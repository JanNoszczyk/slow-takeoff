# wealtharc-turbo-er/wa/ingest/stocktwits.py

import asyncio
import httpx
import pandas as pd
from datetime import datetime, timezone
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed
import duckdb
import json

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

async def store_raw_stocktwits_messages(messages: list[dict], symbol: str, con: duckdb.DuckDBPyConnection):
    """Stores raw StockTwits message JSON payloads."""
    if not messages:
        return

    logger.info(f"Storing {len(messages)} raw StockTwits message payloads for {symbol}...")
    fetched_at = datetime.now(timezone.utc)
    records = []
    for msg in messages:
        # Use message id as the primary key for the raw table
        records.append((str(msg['id']), fetched_at, json.dumps(msg)))

    try:
        con.executemany(
            f"""
            INSERT INTO {RAW_STOCKTWITS_TABLE} (id, fetched_at, payload) VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET fetched_at=excluded.fetched_at, payload=excluded.payload;
            """,
            records
        )
        logger.success(f"Successfully stored/updated {len(records)} raw StockTwits message records.")
    except Exception as e:
        logger.error(f"Error storing raw StockTwits message data: {e}")


async def store_cleaned_stocktwits_messages(messages: list[dict], symbol: str, con: duckdb.DuckDBPyConnection):
    """Stores cleaned StockTwits message data into the database."""
    if not messages:
        return

    logger.info(f"Storing {len(messages)} cleaned StockTwits messages for {symbol}...")
    fetched_at = datetime.now(timezone.utc)
    records_to_insert = []

    for msg in messages:
        # Parse created_at timestamp (StockTwits format: "YYYY-MM-DDTHH:MM:SSZ")
        created_dt = pd.to_datetime(msg['created_at'], format="%Y-%m-%dT%H:%M:%SZ").tz_localize(timezone.utc)
        sentiment = msg.get('entities', {}).get('sentiment', None)
        sentiment_basic = sentiment.get('basic') if sentiment else None

        record = (
            msg['id'],
            symbol,
            msg['user']['id'],
            msg['user']['username'],
            created_dt,
            fetched_at,
            msg['body'],
            sentiment_basic, # 'Bullish' or 'Bearish' or None
            # Potentially add other fields like likes count, reshares count if needed
            # msg.get('likes', {}).get('total', 0)
        )
        records_to_insert.append(record)

    try:
        # Use table name constant once added to db.py
        con.executemany(
            f"""
            INSERT INTO {STOCKTWITS_MESSAGES_TABLE} (
                message_id, symbol, user_id, username, created_at, fetched_at, body, sentiment
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(message_id) DO UPDATE SET
                fetched_at = excluded.fetched_at,
                body = excluded.body, -- Update body in case of edits? Unlikely needed.
                sentiment = excluded.sentiment;
            """,
            records_to_insert
        )
        logger.success(f"Successfully stored/updated {len(records_to_insert)} cleaned StockTwits messages.")
    except Exception as e:
        logger.error(f"Error storing cleaned StockTwits message data: {e}")


# --- Main Ingestion Function ---

async def ingest_stocktwits_symbol(symbol: str, limit: int = 30, con: duckdb.DuckDBPyConnection | None = None):
    """Fetches the latest messages for a symbol from StockTwits and stores them."""
    logger.info(f"Starting StockTwits ingestion for symbol: {symbol}")
    conn_local = con or get_db_connection()

    try:
        messages = await fetch_stocktwits_symbol_stream(symbol, limit=limit)

        if messages:
            # Store raw and cleaned data
            await store_raw_stocktwits_messages(messages, symbol, con=conn_local)
            await store_cleaned_stocktwits_messages(messages, symbol, con=conn_local)
            logger.success(f"Successfully processed {len(messages)} messages for {symbol}.")
        else:
            logger.info(f"No messages found or processed for symbol {symbol}.")

    except Exception as e:
        logger.exception(f"Error during StockTwits ingestion pipeline for symbol {symbol}: {e}")
    finally:
        if not con and conn_local:
            conn_local.close()


# Example Usage
async def main():
    test_symbol = "AAPL"
    conn = get_db_connection()
    try:
        # Ensure schema exists
        from .. import db # Import here for example clarity
        db.create_schema(conn)
        await ingest_stocktwits_symbol(test_symbol, limit=25, con=conn)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    asyncio.run(main())
