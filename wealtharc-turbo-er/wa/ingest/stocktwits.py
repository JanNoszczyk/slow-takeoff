# wealtharc-turbo-er/wa/ingest/stocktwits.py

import asyncio
import httpx
import pandas as pd
from datetime import datetime, timezone
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed
import duckdb
import json
import asyncio # Import asyncio

from ..config import STOCKTWITS_API_KEY # Import specific variable
from ..db import get_db_connection, STOCKTWITS_MESSAGES_TABLE, RAW_STOCKTWITS_TABLE # Import table constants

# StockTwits API v2 Base URL
STOCKTWITS_API_BASE_URL = "https://api.stocktwits.com/api/2/"

# API Key (May be optional for public streams, required for others)
API_KEY = STOCKTWITS_API_KEY # Use imported variable

# Define table names (now imported)
# RAW_STOCKTWITS_TABLE = "raw_stocktwits" # Now imported
# STOCKTWITS_MESSAGES_TABLE = "stocktwits_messages" # Now imported

# --- API Fetching Functions ---

@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
async def fetch_stocktwits_symbol_stream(symbol: str, limit: int = 30, since: int | None = None, max_id: int | None = None) -> list[dict]:
    """
    Fetches the message stream for a specific symbol from StockTwits API v2.

    Args:
        symbol: The stock symbol (e.g., 'AAPL', 'MSFT').
        limit: Number of messages to return (max 30 for free tier?).
        since: Returns results with ID greater than (newer than) this ID.
        max_id: Returns results with ID less than or equal to (older than) this ID.

    Returns:
        A list of message data dictionaries or an empty list.
    """
    endpoint = f"streams/symbol/{symbol}.json"
    url = f"{STOCKTWITS_API_BASE_URL}{endpoint}"
    params = {"limit": min(30, limit)} # API max seems to be 30
    if since:
        params["since"] = since
    if max_id:
        params["max"] = max_id
    # Add API key if provided/required
    # if API_KEY:
    #     params["access_token"] = API_KEY

    logger.info(f"Fetching StockTwits stream for symbol: {symbol}, params: {params}")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, timeout=30.0)
            response.raise_for_status()
            data = response.json()

            if response.status_code == 200 and data.get("response", {}).get("status") == 200:
                messages = data.get("messages", [])
                logger.success(f"Successfully fetched {len(messages)} messages for {symbol} from StockTwits.")
                return messages
            else:
                error_msg = data.get("errors", [{}])[0].get("message", "Unknown StockTwits API error")
                logger.error(f"StockTwits API error for {symbol}: {error_msg} (Status: {response.status_code})")
                return []

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching StockTwits stream for {symbol}: {e.response.status_code} - {e.request.url}")
            # Specific handling for 404 (symbol not found) vs 429 (rate limit) could be added
            if e.response.status_code == 429:
                logger.warning("StockTwits rate limit likely hit. Retrying based on tenacity settings.")
                raise # Reraise to trigger retry
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching StockTwits stream for {symbol}: {e}")
            return []


# --- Database Storage Functions ---

async def store_raw_stocktwits_messages(messages: list[dict], symbol: str, db_path: str | None = None):
    """Stores raw StockTwits message JSON payloads."""
    if not messages:
        return

    logger.info(f"Storing {len(messages)} raw StockTwits message payloads for {symbol}...")
    fetched_at = datetime.now(timezone.utc)
    records = []
    for msg in messages:
        records.append((str(msg['id']), fetched_at, json.dumps(msg)))

    try:
        # Define DB operation to run in thread, including connection management
        def db_operations_in_thread(path: str | None, data: list):
            conn = None
            try:
                conn = get_db_connection(path) # Create connection inside thread
                sql = f"""
                    INSERT INTO {RAW_STOCKTWITS_TABLE} (id, fetched_at, payload) VALUES (?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET fetched_at=excluded.fetched_at, payload=excluded.payload;
                    """
                conn.executemany(sql, data) # Use connection
                logger.success(f"Thread successfully stored/updated {len(data)} raw StockTwits records.")
            except Exception as thread_e:
                logger.error(f"Error in thread storing raw StockTwits data: {thread_e}")
                raise # Re-raise exception to be caught by the main async task
            finally:
                if conn:
                    conn.close() # Close connection inside thread
                    logger.debug("Thread closed raw StockTwits DB connection.")

        # Run the entire operation (connect, execute, close) in a separate thread
        await asyncio.to_thread(db_operations_in_thread, db_path, records)

    except Exception as e:
        # Log error raised from the thread
        logger.error(f"Error storing raw StockTwits data: {e}")
        raise # Re-raise to be caught by the calling ingestor function


async def store_cleaned_stocktwits_messages(messages: list[dict], symbol: str, db_path: str | None = None):
    """Stores cleaned StockTwits message data into the database."""
    if not messages:
        return

    logger.info(f"Storing {len(messages)} cleaned StockTwits messages for {symbol}...")
    fetched_at = datetime.now(timezone.utc)
    # Prepare data without symbol, asset_id will be fetched in the thread
    messages_data = []
    for msg in messages:
        created_dt = pd.to_datetime(msg['created_at'], format="%Y-%m-%dT%H:%M:%SZ").tz_localize(timezone.utc)
        sentiment = msg.get('entities', {}).get('sentiment', None)
        sentiment_basic = sentiment.get('basic') if sentiment else None
        messages_data.append({
            'message_id': msg['id'],
            'user_id': msg['user']['id'],
            'username': msg['user']['username'],
            'created_at': created_dt,
            'fetched_at': fetched_at,
            'body': msg['body'],
            'sentiment': sentiment_basic,
        })

    try:
        # Define DB operation to run in thread, including connection management
        def db_operations_in_thread(path: str | None, current_symbol: str, data_list: list[dict]):
            conn = None
            inserted_count = 0
            try:
                conn = get_db_connection(path) # Create connection inside thread

                # 1. Get asset_id for the current symbol
                asset_id_result = conn.execute("SELECT asset_id FROM assets WHERE ticker = ?", (current_symbol,)).fetchone()
                if not asset_id_result:
                    logger.warning(f"Thread could not find asset_id for symbol '{current_symbol}'. Skipping cleaned data insertion.")
                    return 0 # Indicate 0 insertions
                asset_id = asset_id_result[0]

                # 2. Prepare records with asset_id
                records_with_asset_id = []
                for msg_data in data_list:
                    records_with_asset_id.append((
                        msg_data['message_id'],
                        asset_id, # Use fetched asset_id
                        msg_data['user_id'],
                        msg_data['username'],
                        msg_data['created_at'],
                        msg_data['fetched_at'],
                        msg_data['body'],
                        msg_data['sentiment'],
                    ))

                # 3. Execute INSERT statement with asset_id
                sql = f"""
                    INSERT INTO {STOCKTWITS_MESSAGES_TABLE} (
                        message_id, asset_id, user_id, username, created_at, fetched_at, body, sentiment
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(message_id) DO UPDATE SET
                        fetched_at = excluded.fetched_at,
                        asset_id = excluded.asset_id, -- Ensure asset_id is updated on conflict too
                        body = excluded.body,
                        sentiment = excluded.sentiment;
                    """
                conn.executemany(sql, records_with_asset_id) # Use connection
                inserted_count = len(records_with_asset_id)
                logger.success(f"Thread successfully stored/updated {inserted_count} cleaned StockTwits records for asset_id {asset_id}.")
                return inserted_count # Return count of processed records
            except Exception as thread_e:
                logger.error(f"Error in thread storing cleaned StockTwits data for {current_symbol}: {thread_e}")
                raise # Re-raise exception to be caught by asyncio.to_thread
            finally:
                if conn:
                    conn.close() # Close connection inside thread
                    logger.debug(f"Thread closed cleaned StockTwits DB connection for {current_symbol}.")

        # Run the entire operation (connect, fetch asset_id, execute, close) in a separate thread
        # Pass the symbol and the prepared message data list
        await asyncio.to_thread(db_operations_in_thread, db_path, symbol, messages_data)

    except Exception as e:
        # Log error raised from the thread
        logger.error(f"Error storing cleaned StockTwits data: {e}")
        raise # Re-raise


# --- Main Ingestion Function ---

async def ingest_stocktwits_symbol(symbol: str, limit: int = 30, db_path: str | None = None):
    """Fetches the latest messages for a symbol from StockTwits and stores them."""
    logger.info(f"Starting StockTwits ingestion for symbol: {symbol}")

    try:
        messages = await fetch_stocktwits_symbol_stream(symbol, limit=limit)

        if messages:
            # Pass db_path to storage functions; they handle connections & threading
            try:
                 # Use await directly on the storage functions
                 await store_raw_stocktwits_messages(messages, symbol, db_path=db_path)
                 await store_cleaned_stocktwits_messages(messages, symbol, db_path=db_path)
                 logger.success(f"Successfully processed {len(messages)} messages for {symbol}.")
            except Exception as store_e:
                 # Catch errors raised from the storage functions (which caught thread errors)
                 logger.error(f"Failed to store StockTwits data for {symbol}: {store_e}", exc_info=True)
        else:
            logger.info(f"No messages found or processed for symbol {symbol}.")

    except Exception as e:
        logger.exception(f"Error during StockTwits ingestion pipeline for symbol {symbol}: {e}")
        # Raise other unexpected errors from fetching etc.
        raise


# Example Usage
async def main():
    test_symbol = "AAPL"
    # Example needs update - should pass db_path, not con
    test_db_path = "test_stocktwits.db"
    conn = get_db_connection(test_db_path)
    try:
        # Ensure schema exists
        from .. import db # Import here for example clarity
        db.create_schema(conn)
        conn.close() # Close schema check connection
        await ingest_stocktwits_symbol(test_symbol, limit=25, db_path=test_db_path) # Pass db_path
    finally:
        # Clean up test db file
        import os
        if os.path.exists(test_db_path):
             os.remove(test_db_path)

if __name__ == "__main__":
    asyncio.run(main())
