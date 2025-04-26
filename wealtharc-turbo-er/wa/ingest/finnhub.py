import asyncio
import httpx
import json
import time
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from wa import config, db

FINNHUB_API_URL = "https://finnhub.io/api/v1"
# Finnhub rate limits (free plan): 60 calls/minute
# Consider batching requests or adding delays if needed.

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    reraise=True
)
async def get_finnhub_quote(symbol: str, client: httpx.AsyncClient) -> Optional[Dict[str, Any]]:
    """
    Fetches the latest quote for a given symbol from Finnhub.

    Args:
        symbol: The stock ticker symbol (e.g., "AAPL").
        client: An httpx.AsyncClient instance.

    Returns:
        A dictionary containing the quote data, or None if failed.
        Example Finnhub quote structure:
        {
          "c": 261.74,      # Current price
          "d": -0.09,       # Change
          "dp": -0.0344,    # Percent change
          "h": 263.31,      # High price of the day
          "l": 260.68,      # Low price of the day
          "o": 261.07,      # Open price of the day
          "pc": 261.83,     # Previous close price
          "t": 1582675200   # Timestamp (Unix seconds)
        }
    """
    if not config.FINNHUB_API_KEY:
        logger.error("FINNHUB_API_KEY not set. Cannot fetch quotes.")
        return None
    if not symbol:
        logger.warning("No symbol provided for Finnhub quote.")
        return None

    params = {
        "symbol": symbol,
        "token": config.FINNHUB_API_KEY
    }
    url = f"{FINNHUB_API_URL}/quote"

    try:
        response = await client.get(url, params=params, timeout=config.HTTPX_TIMEOUT)
        response.raise_for_status()
        quote_data = response.json()

        # Finnhub returns 't': 0 if no data found or other issues
        if quote_data.get('t') == 0 and quote_data.get('c') == 0:
            logger.warning(f"Finnhub returned zero data for symbol '{symbol}'. May be invalid or delisted.")
            return None

        logger.debug(f"Finnhub quote received for symbol '{symbol}'. Price: {quote_data.get('c')}")
        return quote_data

    except httpx.HTTPStatusError as e:
        logger.error(f"Finnhub API request for '{symbol}' failed with status {e.response.status_code}: {e.response.text}")
        if e.response.status_code == 429: # Rate limit
            logger.warning("Finnhub rate limit likely exceeded. Consider adding delays or upgrading plan.")
        elif e.response.status_code == 401: # Invalid API key
             logger.error("Finnhub API key is invalid or expired.")
        # Let tenacity handle retries for relevant status codes
        raise
    except httpx.RequestError as e:
        logger.error(f"Network error contacting Finnhub API for '{symbol}': {e}")
        raise # Let tenacity handle retries
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode Finnhub API JSON response for '{symbol}': {e}")
        return None # Don't retry on decode error
    except Exception as e:
        logger.error(f"Unexpected error during Finnhub quote request for '{symbol}': {e}")
        return None # Don't retry unknown errors


def store_raw_finnhub_quote(symbol: str, quote_data: Dict[str, Any], con: duckdb.DuckDBPyConnection):
    """Stores the raw quote data in the raw_finnhub table."""
    if not quote_data or not symbol:
        return 0

    now_ts = datetime.now(timezone.utc)
    # Use symbol + timestamp as a unique ID for the raw entry
    ts = quote_data.get('t', int(now_ts.timestamp()))
    raw_id = f"finnhub_{symbol}_{ts}"

    insert_sql = """
        INSERT INTO raw_finnhub (id, fetched_at, payload)
        VALUES (?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            fetched_at = excluded.fetched_at,
            payload = excluded.payload;
    """
    try:
        con.execute(insert_sql, [raw_id, now_ts, json.dumps(quote_data)])
        logger.debug(f"Stored raw Finnhub quote for '{symbol}' with id {raw_id}.")
        return 1
    except Exception as e:
        logger.error(f"Failed to store raw Finnhub quote for '{symbol}': {e}")
        return 0


def store_clean_finnhub_quote(symbol: str, quote_data: Dict[str, Any], con: duckdb.DuckDBPyConnection):
    """Stores the cleaned quote data in the 'quotes' table, linking via ticker symbol."""
    if not quote_data or not symbol:
        return 0

    price = quote_data.get('c') # Current price
    volume = quote_data.get('volume') # Finnhub quote endpoint doesn't usually provide volume, need trade data
    timestamp_sec = quote_data.get('t')

    if price is None or timestamp_sec is None or timestamp_sec == 0:
        logger.warning(f"Missing price or valid timestamp in Finnhub data for '{symbol}'. Skipping clean storage.")
        return 0

    ts_dt = datetime.fromtimestamp(timestamp_sec, tz=timezone.utc)
    now_ts = datetime.now(timezone.utc)

    # Find asset_id by ticker symbol - this is a simplification.
    # A robust system would use FIGI or other unique IDs resolved earlier.
    try:
        asset_row = con.sql("SELECT asset_id FROM assets WHERE ticker = ? LIMIT 1", [symbol]).fetchone()
        if not asset_row:
            logger.warning(f"Could not find asset_id for ticker '{symbol}' in assets table. Quote not stored in clean table.")
            # Optionally, create a placeholder asset entry here if desired
            return 0
        asset_id = asset_row[0]
    except Exception as e:
        logger.error(f"Error looking up asset_id for ticker '{symbol}': {e}")
        return 0

    insert_sql = """
        INSERT INTO quotes (asset_id, ts, price, volume, source, fetched_at)
        VALUES (?, ?, ?, ?, 'finnhub', ?)
        ON CONFLICT (asset_id, ts, source) DO UPDATE SET
            price = excluded.price,
            volume = excluded.volume,
            fetched_at = excluded.fetched_at;
    """
    try:
        con.execute(insert_sql, [asset_id, ts_dt, price, volume, now_ts])
        logger.debug(f"Stored clean Finnhub quote for asset_id={asset_id} ('{symbol}') at {ts_dt}.")
        return 1
    except Exception as e:
        logger.error(f"Failed to store clean Finnhub quote for asset_id={asset_id} ('{symbol}'): {e}")
        return 0


async def ingest_finnhub_quotes(symbols: List[str], con: duckdb.DuckDBPyConnection = None):
    """
    High-level function to fetch quotes for a list of symbols, store raw data,
    and store clean data.

    Args:
        symbols: List of ticker symbols (e.g., ["AAPL", "MSFT"]).
        con: Optional DuckDB connection.
    """
    if not symbols:
        logger.info("No symbols provided for Finnhub quote ingestion.")
        return
    if not config.FINNHUB_API_KEY:
        logger.error("FINNHUB_API_KEY not set. Aborting Finnhub ingestion.")
        return

    close_conn_locally = False
    if con is None:
        con = db.get_db_connection()
        close_conn_locally = True

    total_raw_stored = 0
    total_clean_stored = 0
    processed_symbols = 0
    start_time = time.time()
    # Use a longer timeout for the client if fetching many symbols
    timeout = httpx.Timeout(config.HTTPX_TIMEOUT, pool=None)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            tasks = []
            for symbol in symbols:
                tasks.append(get_finnhub_quote(symbol, client))
                # Add a small delay to help manage rate limits, even within async calls
                await asyncio.sleep(60 / 55) # Aim slightly below 60 calls/min

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(results):
                symbol = symbols[i]
                processed_symbols += 1
                if isinstance(result, Exception):
                    logger.error(f"Failed to fetch Finnhub quote for '{symbol}' after retries: {result}")
                elif result:
                    raw_stored = store_raw_finnhub_quote(symbol, result, con)
                    total_raw_stored += raw_stored
                    if raw_stored:
                         total_clean_stored += store_clean_finnhub_quote(symbol, result, con)
                else:
                    # Already logged warning/error inside get_finnhub_quote if None was returned
                    logger.debug(f"No valid quote data returned for '{symbol}'.")

    except Exception as e:
        logger.error(f"An unexpected error occurred during Finnhub ingestion: {e}")
    finally:
        end_time = time.time()
        logger.info(f"Finnhub quote ingestion finished for {processed_symbols} symbols in {end_time - start_time:.2f}s. Stored {total_raw_stored} raw, {total_clean_stored} clean quotes.")
        if close_conn_locally:
            db.close_db_connection()


if __name__ == "__main__":
    # Example usage: Fetch quotes for a few tickers
    example_symbols = ["AAPL", "MSFT", "TSLA", "NVDA", "NONEXISTENT"]

    # Make sure the DB schema exists and potentially add assets first
    try:
        conn = db.get_db_connection()
        db.create_schema(conn)
        # Add dummy assets if needed for the clean storage part to work
        logger.info("Checking/adding dummy assets for Finnhub example...")
        conn.sql("""
            INSERT INTO assets (asset_id, name, ticker) VALUES
            (1, 'Apple Inc.', 'AAPL'),
            (2, 'Microsoft Corporation', 'MSFT'),
            (3, 'Tesla, Inc.', 'TSLA'),
            (4, 'NVIDIA Corporation', 'NVDA')
            ON CONFLICT (asset_id) DO NOTHING;
        """)
        logger.info("Dummy assets checked/added.")
        asyncio.run(ingest_finnhub_quotes(example_symbols, con=conn))
    except Exception as e:
        logger.error(f"Main execution error: {e}")
    finally:
        db.close_db_connection()
