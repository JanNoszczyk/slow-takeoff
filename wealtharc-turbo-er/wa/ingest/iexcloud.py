import asyncio
import httpx
from datetime import datetime, timezone # Moved import here
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed
from typing import List, Dict, Any

from wa.config import settings
from wa.db import get_db_connection

# Base URL for IEX Cloud API (adjust if using sandbox or specific version)
IEX_BASE_URL = "https://cloud.iexapis.com/stable"

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def fetch_iex_data(endpoint: str, params: Dict[str, Any] = None) -> Any:
    """Fetches data from a specific IEX Cloud endpoint."""
    if not settings.IEX_CLOUD_API_KEY:
        logger.warning("IEX_CLOUD_API_KEY not set. Skipping IEX Cloud fetch.")
        return None

    base_params = {"token": settings.IEX_CLOUD_API_KEY}
    if params:
        base_params.update(params)

    url = f"{IEX_BASE_URL}/{endpoint}"
    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"Fetching data from IEX Cloud endpoint: {endpoint} with params: {params}")
            response = await client.get(url, params=base_params)
            response.raise_for_status()
            logger.success(f"Successfully fetched data from {endpoint}")
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching {url}: {e.response.status_code} - {e.response.text}")
            raise  # Re-raise to trigger tenacity retry
        except Exception as e:
            logger.error(f"Error fetching data from {endpoint}: {e}")
            raise # Re-raise to trigger tenacity retry

async def store_raw_iex_quote(conn, symbol: str, data: Any):
    """Stores the raw quote data from IEX Cloud."""
    if data:
        logger.debug(f"Storing raw IEX quote for {symbol}")
        await conn.execute("""
            INSERT INTO raw_iex_quotes (symbol, timestamp, payload)
            VALUES ($1, CURRENT_TIMESTAMP, $2)
            ON CONFLICT (symbol) DO UPDATE SET
                timestamp = excluded.timestamp,
                payload = excluded.payload;
        """, symbol, str(data)) # Store payload as string/JSONB
        logger.success(f"Stored raw IEX quote for {symbol}")

async def parse_and_store_iex_quote(conn, symbol: str, raw_data: Dict[str, Any]):
    """Parses raw IEX quote data and stores it in the cleaned quotes table."""
    # Example parsing logic - adjust based on the actual quote endpoint response structure
    # Common quote endpoints might be /stock/{symbol}/quote
    if not raw_data:
        logger.warning(f"No raw data provided for IEX quote parsing for {symbol}.")
        return

    try:
        # Adjust fields based on IEX Cloud quote response
        price = raw_data.get('latestPrice')
        volume = raw_data.get('latestVolume')
        timestamp_ms = raw_data.get('latestUpdate') # Assuming ms timestamp

        if price is None or timestamp_ms is None:
            logger.warning(f"Missing essential fields (price, timestamp) in IEX raw data for {symbol}. Raw: {raw_data}")
            return

        # Convert timestamp if necessary (IEX often provides ms epoch)
        quote_timestamp = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)

        logger.debug(f"Parsing and storing cleaned IEX quote for {symbol}: Price={price}, Vol={volume}, TS={quote_timestamp}")
        # Use existing quotes table structure
        await conn.execute("""
            INSERT INTO quotes (asset_id, timestamp, source, price, volume)
            SELECT id, $2, 'IEX Cloud', $3, $4 FROM assets WHERE iex_symbol = $1 -- Assuming an iex_symbol column exists or using primary symbol
            ON CONFLICT (asset_id, timestamp, source) DO NOTHING;
        """, symbol, quote_timestamp, price, volume)
        logger.success(f"Stored cleaned IEX quote for {symbol} at {quote_timestamp}")

    except Exception as e:
        logger.error(f"Error parsing/storing IEX quote for {symbol}: {e}\nRaw data: {raw_data}")


async def ingest_iex_quotes(symbols: List[str]):
    """Fetches and stores quotes for a list of symbols from IEX Cloud."""
    logger.info(f"Starting IEX Cloud quote ingestion for symbols: {symbols}")
    conn = None
    try:
        conn = await get_db_connection()
        tasks = []
        for symbol in symbols:
            # Example: Fetching basic quote data. Adjust endpoint as needed.
            # Common endpoint is /stock/{symbol}/quote
            # Or use batch requests: /stock/market/batch?symbols=aapl,tsla&types=quote
            # Consider batching for efficiency if API supports it well.
            tasks.append(process_single_iex_quote(conn, symbol))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                logger.error(f"Error processing IEX quote for {symbol}: {result}")
            else:
                logger.success(f"Successfully processed IEX quote for {symbol}")

    except Exception as e:
        logger.error(f"Failed IEX Cloud quote ingestion: {e}")
    finally:
        if conn:
            await conn.close()
            logger.info("Database connection closed for IEX Cloud ingest.")

async def process_single_iex_quote(conn, symbol: str):
    """Fetches, stores raw, parses and stores cleaned quote for one symbol."""
    try:
        # Adjust the endpoint based on desired data (e.g., 'quote', 'chart')
        endpoint = f"stock/{symbol}/quote"
        raw_data = await fetch_iex_data(endpoint)
        if raw_data:
            await store_raw_iex_quote(conn, symbol, raw_data)
            # Datetime/timezone now imported at top
            await parse_and_store_iex_quote(conn, symbol, raw_data)
        else:
            logger.warning(f"No data received from IEX Cloud for symbol {symbol}")
    except Exception as e:
        logger.error(f"Error processing single IEX quote for {symbol}: {e}")
        raise # Propagate error for gather
```

I will now wait for confirmation that this file was created successfully before proceeding to the next step (updating `wa/db.py`).
