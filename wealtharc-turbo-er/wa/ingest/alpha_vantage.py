import asyncio
import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed
from typing import List, Dict, Any
from datetime import datetime, timezone, date

from wa.config import settings
from wa.db import get_db_connection

# Base URL for Alpha Vantage API
ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"

# Note: Alpha Vantage free tier has strict rate limits (e.g., 5 calls/min, 500 calls/day).
# Implement appropriate delays or use a paid plan for higher volume.
# Tenacity retry might help with transient errors but not strict rate limits over time.
# Consider adding an asyncio.sleep(12) between calls in the main loop for the free tier.

@retry(stop=stop_after_attempt(3), wait=wait_fixed(3)) # Wait a bit longer due to potential rate limits
async def fetch_alpha_vantage_data(params: Dict[str, Any]) -> Any:
    """Fetches data from Alpha Vantage API."""
    if not settings.ALPHAVANTAGE_API_KEY: # Corrected variable name
        logger.warning("ALPHAVANTAGE_API_KEY not set. Skipping Alpha Vantage fetch.")
        return None

    base_params = {"apikey": settings.ALPHAVANTAGE_API_KEY} # Corrected variable name
    base_params.update(params)

    async with httpx.AsyncClient(timeout=30.0) as client: # Increase timeout slightly
        try:
            logger.info(f"Fetching data from Alpha Vantage with params: {params}")
            response = await client.get(ALPHA_VANTAGE_BASE_URL, params=base_params)
            response.raise_for_status()
            data = response.json()
            # Check for API error messages within the JSON response
            if "Error Message" in data:
                logger.error(f"Alpha Vantage API error: {data['Error Message']}")
                return None
            if "Information" in data and 'rate limit' in data['Information'].lower():
                logger.warning(f"Alpha Vantage rate limit potentially hit: {data['Information']}")
                # Consider raising a specific exception here if you want to handle rate limits differently
                # For now, just return None and let retry handle potential recovery
                return None # Treat rate limit info like an error for retry purposes

            logger.success(f"Successfully fetched data from Alpha Vantage for function: {params.get('function')}")
            return data
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching Alpha Vantage: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.ReadTimeout:
            logger.warning("Read timeout fetching Alpha Vantage. Retrying...")
            raise
        except Exception as e:
            logger.error(f"Error fetching data from Alpha Vantage: {e}")
            raise

async def store_raw_alpha_vantage_quote(conn, symbol: str, data: Any):
    """Stores the raw quote data from Alpha Vantage."""
    if data:
        # Use symbol and function as part of ID? Or just symbol? Global Quote is simple.
        raw_id = f"alphavantage_globalquote_{symbol}"
        logger.debug(f"Storing raw Alpha Vantage quote for {symbol}")
        await conn.execute("""
            INSERT INTO raw_alpha_vantage (id, fetched_at, payload)
            VALUES ($1, CURRENT_TIMESTAMP, $2::JSON) -- Ensure payload is stored as JSON
            ON CONFLICT (id) DO UPDATE SET
                fetched_at = excluded.fetched_at,
                payload = excluded.payload;
        """, raw_id, str(data)) # Pass data as string for JSON conversion
        logger.success(f"Stored raw Alpha Vantage quote for {symbol}")

async def parse_and_store_alpha_vantage_quote(conn, symbol: str, raw_data: Dict[str, Any]):
    """Parses raw Alpha Vantage GLOBAL_QUOTE data and stores it in the cleaned quotes table."""
    if not raw_data or "Global Quote" not in raw_data:
        logger.warning(f"Invalid or missing 'Global Quote' data for Alpha Vantage parsing for {symbol}.")
        return

    quote_data = raw_data["Global Quote"]

    try:
        # Alpha Vantage GLOBAL_QUOTE fields (check API docs for exact names)
        price_str = quote_data.get('05. price')
        volume_str = quote_data.get('06. volume')
        date_str = quote_data.get('07. latest trading day') # Date only, no time

        if price_str is None or date_str is None:
            logger.warning(f"Missing essential fields (price, date) in Alpha Vantage Global Quote for {symbol}. Raw: {quote_data}")
            return

        price = float(price_str)
        volume = float(volume_str) if volume_str is not None else None
        # Assume the quote is for the *end* of the 'latest trading day'. Use 23:59:59 UTC? Or market close time?
        # Using end of day UTC is simpler without market time knowledge.
        quote_date = date.fromisoformat(date_str)
        # Combine date with a fixed time (e.g., end of day UTC)
        quote_timestamp = datetime.combine(quote_date, datetime.max.time(), tzinfo=timezone.utc)


        logger.debug(f"Parsing and storing cleaned Alpha Vantage quote for {symbol}: Price={price}, Vol={volume}, TS={quote_timestamp}")
        # Use existing quotes table structure. Assume 'ticker' in assets matches AV symbol.
        await conn.execute("""
            INSERT INTO quotes (asset_id, ts, source, price, volume, fetched_at)
            SELECT id, $2, 'Alpha Vantage', $3, $4, CURRENT_TIMESTAMP FROM assets WHERE ticker = $1 -- Or use alpha_vantage_symbol if added
            ON CONFLICT (asset_id, ts, source) DO NOTHING;
        """, symbol, quote_timestamp, price, volume)
        logger.success(f"Stored cleaned Alpha Vantage quote for {symbol} at {quote_timestamp}")

    except Exception as e:
        logger.error(f"Error parsing/storing Alpha Vantage quote for {symbol}: {e}\nRaw quote data: {quote_data}")


async def ingest_alpha_vantage_quotes(symbols: List[str]):
    """Fetches and stores quotes for a list of symbols from Alpha Vantage."""
    logger.info(f"Starting Alpha Vantage quote ingestion for symbols: {symbols}")
    conn = None
    try:
        conn = await get_db_connection()
        tasks = []
        for i, symbol in enumerate(symbols):
            # Add delay for free tier rate limiting (e.g., 1 call every 12 seconds)
            if i > 0:
                 free_tier_delay = 13 # Slightly more than 12s
                 logger.debug(f"Alpha Vantage free tier delay: sleeping for {free_tier_delay} seconds...")
                 await asyncio.sleep(free_tier_delay)

            tasks.append(process_single_alpha_vantage_quote(conn, symbol))

        # Run tasks sequentially due to rate limits, gather might overwhelm the free tier API
        results = []
        for task in tasks:
            try:
                result = await task
                results.append(result)
            except Exception as e:
                results.append(e) # Store exception

        # Log results after all attempts
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                logger.error(f"Error processing Alpha Vantage quote for {symbol}: {result}")
            elif result is False: # Check if process_single returned False for handled errors
                 logger.warning(f"Skipped or failed processing Alpha Vantage quote for {symbol} (check previous logs).")
            else:
                logger.success(f"Successfully processed Alpha Vantage quote for {symbol}")

    except Exception as e:
        logger.error(f"Failed Alpha Vantage quote ingestion: {e}")
    finally:
        if conn:
            await conn.close()
            logger.info("Database connection closed for Alpha Vantage ingest.")

async def process_single_alpha_vantage_quote(conn, symbol: str) -> bool:
    """Fetches, stores raw, parses and stores cleaned quote for one symbol from Alpha Vantage."""
    try:
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": symbol
        }
        raw_data = await fetch_alpha_vantage_data(params)
        if raw_data:
            await store_raw_alpha_vantage_quote(conn, symbol, raw_data)
            await parse_and_store_alpha_vantage_quote(conn, symbol, raw_data)
            return True # Indicate success
        else:
            logger.warning(f"No data received or API error from Alpha Vantage for symbol {symbol}")
            return False # Indicate handled failure/skip
    except Exception as e:
        logger.error(f"Error processing single Alpha Vantage quote for {symbol}: {e}")
        # Don't re-raise here if called sequentially, just return False
        return False # Indicate unhandled failure
```

I'll wait for confirmation that this file `wealtharc-turbo-er/wa/ingest/alpha_vantage.py` was created successfully. Then I will proceed to update `wa/config.py`.
