import asyncio
import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from wa.config import settings
from wa.db import get_db_connection

# Base URL for Open Exchange Rates API
OER_BASE_URL = "https://openexchangerates.org/api"

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def fetch_oer_data(endpoint: str = "latest.json", params: Optional[Dict[str, Any]] = None) -> Any:
    """Fetches data from the Open Exchange Rates API."""
    if not settings.OPENEXCHANGERATES_APP_ID:
        logger.warning("OPENEXCHANGERATES_APP_ID not set. Skipping OER fetch.")
        return None

    base_params = {"app_id": settings.OPENEXCHANGERATES_APP_ID}
    if params:
        base_params.update(params)

    url = f"{OER_BASE_URL}/{endpoint}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            logger.info(f"Fetching data from OER endpoint: {endpoint} with params: {params}")
            response = await client.get(url, params=base_params)
            response.raise_for_status()
            data = response.json()

            # Check for API errors within the response
            if data.get("error"):
                logger.error(f"OER API Error: {data.get('status')} - {data.get('message')}: {data.get('description')}")
                return None

            logger.success(f"Successfully fetched data from OER endpoint {endpoint}")
            return data
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching {url}: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error fetching data from {endpoint}: {e}")
            raise

async def store_raw_oer_data(conn, endpoint: str, data: Any):
    """Stores the raw OER data."""
    if data:
        # Use endpoint and timestamp? Or just 'latest'?
        # Base currency might change if not using free plan.
        base_currency = data.get("base", "USD") # OER free plan uses USD base
        timestamp = data.get("timestamp", int(datetime.now(timezone.utc).timestamp()))
        raw_id = f"oer_{endpoint.replace('.json','')}_{base_currency}_{timestamp}"
        logger.debug(f"Storing raw OER data for {endpoint} at {timestamp}")
        await conn.execute("""
            INSERT INTO raw_open_exchange_rates (id, fetched_at, payload)
            VALUES ($1, CURRENT_TIMESTAMP, $2::JSON)
            ON CONFLICT (id) DO UPDATE SET
                fetched_at = excluded.fetched_at,
                payload = excluded.payload;
        """, raw_id, str(data)) # Pass data as string for JSON conversion
        logger.success(f"Stored raw OER {endpoint} data")

async def parse_and_store_oer_rates(conn, raw_data: Dict[str, Any]):
    """Parses raw OER data (latest.json or historical) and stores it in the fx_rates table."""
    if not raw_data or "rates" not in raw_data or "timestamp" not in raw_data:
        logger.warning("Invalid or missing 'rates'/'timestamp' in OER raw data.")
        return False

    try:
        oer_timestamp_unix = raw_data["timestamp"]
        base_currency = raw_data.get("base", "USD") # Free plan base is USD
        rates = raw_data["rates"]
        source = "openexchangerates"

        rate_timestamp = datetime.fromtimestamp(oer_timestamp_unix, tz=timezone.utc)

        rows_to_insert = []
        for quote_currency, rate in rates.items():
            if quote_currency and rate is not None:
                try:
                    rows_to_insert.append((
                        base_currency,
                        quote_currency,
                        rate_timestamp,
                        float(rate),
                        source
                    ))
                except (ValueError, TypeError) as e:
                    logger.warning(f"Skipping OER rate for {quote_currency} due to parsing error: {e}. Rate value: {rate}")
                    continue

        if not rows_to_insert:
            logger.warning("No valid rates processed from OER data.")
            return True # Not necessarily an error

        logger.info(f"Inserting/updating {len(rows_to_insert)} FX rates from OER (Base: {base_currency}, TS: {rate_timestamp})")
        await conn.executemany("""
            INSERT INTO fx_rates (base_currency, quote_currency, ts, rate, source, fetched_at)
            VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP)
            ON CONFLICT (base_currency, quote_currency, ts, source) DO UPDATE SET
                rate = excluded.rate,
                fetched_at = excluded.fetched_at;
        """, rows_to_insert)
        logger.success(f"Successfully stored {len(rows_to_insert)} OER FX rates.")
        return True

    except Exception as e:
        logger.error(f"Error parsing/storing OER rates: {e}\nRaw data sample: {str(raw_data)[:500]}...")
        return False

async def ingest_oer_latest_rates():
    """Fetches the latest exchange rates from Open Exchange Rates."""
    logger.info("Starting OER latest rates ingestion...")
    conn = None
    try:
        conn = await get_db_connection()
        latest_data = await fetch_oer_data(endpoint="latest.json")

        if latest_data:
            await store_raw_oer_data(conn, "latest.json", latest_data)
            success = await parse_and_store_oer_rates(conn, latest_data)
            if success:
                logger.success("OER latest rates ingestion completed successfully.")
            else:
                logger.error("OER latest rates ingestion failed during parsing/storing.")
        else:
            logger.error("Failed to fetch latest rates from OER.")

    except Exception as e:
        logger.error(f"General error during OER latest rates ingestion: {e}")
    finally:
        if conn:
            await conn.close()
            logger.info("Database connection closed for OER ingest.")

# Optional: Add function for historical data if needed
# async def ingest_oer_historical_rates(date_str: str): ...

# Example usage (optional):
# if __name__ == "__main__":
#     async def main():
#         await ingest_oer_latest_rates()
#     asyncio.run(main())
```

I'll wait for confirmation that `wealtharc-turbo-er/wa/ingest/openexchangerates.py` was created successfully. Then, I'll update the Streamlit app.
