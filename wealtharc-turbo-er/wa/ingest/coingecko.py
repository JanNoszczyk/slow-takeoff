import asyncio
import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed, wait_random_exponential
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date, timezone, timedelta
import time
import pandas as pd

from wa.config import settings # No API key needed for free tier
from wa.db import get_db_connection

# Base URL for CoinGecko API
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"

# CoinGecko free tier rate limits are around 10-50 calls/minute.
# Use delays and robust retries.

@retry(
    stop=stop_after_attempt(5), # More attempts for rate limit issues
    wait=wait_random_exponential(multiplier=1, min=2, max=10), # Exponential backoff
    retry_error_callback=lambda retry_state: logger.warning(f"Retrying CoinGecko fetch after error: {retry_state.outcome.exception()}")
)
async def fetch_coingecko_data(endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """Fetches data from the CoinGecko API."""
    url = f"{COINGECKO_BASE_URL}/{endpoint}"

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            # Add small delay before each request to manage rate limits proactively
            await asyncio.sleep(1.5) # ~40 calls/min theoretical max
            logger.info(f"Fetching data from CoinGecko: {url} with params: {params}")
            response = await client.get(url, params=params)

            # Check for 429 Too Many Requests explicitly
            if response.status_code == 429:
                logger.warning("CoinGecko API rate limit hit (429). Retrying after delay...")
                # Extract retry-after header if available, otherwise use default retry wait
                retry_after = response.headers.get("Retry-After")
                wait_time = int(retry_after) if retry_after and retry_after.isdigit() else 15 # Default wait 15s
                logger.warning(f"Waiting for {wait_time} seconds before retry.")
                await asyncio.sleep(wait_time + 1) # Add a buffer
                response.raise_for_status() # Force a retry via tenacity

            response.raise_for_status() # Raise for other HTTP errors
            data = response.json()

            # CoinGecko doesn't usually wrap errors in JSON for successful status codes
            logger.success(f"Successfully fetched data from CoinGecko endpoint {endpoint}")
            return data

        except httpx.HTTPStatusError as e:
            # Log specific error, tenacity will handle retry
            logger.error(f"HTTP error fetching {url}: Status {e.response.status_code}. Response: {e.response.text[:200]}")
            raise
        except Exception as e:
            logger.error(f"Error fetching data from {url}: {e}")
            raise

async def store_raw_coingecko_data(conn, coin_id: str, endpoint: str, data: Any):
    """Stores the raw CoinGecko API response."""
    if data:
        # Create a raw ID based on coin, endpoint, and maybe timestamp if historical
        timestamp_str = str(int(time.time())) # Rough timestamp for ID uniqueness
        raw_id = f"coingecko_{coin_id}_{endpoint.replace('/', '_')}_{timestamp_str}"
        logger.debug(f"Storing raw CoinGecko data for {coin_id} - {endpoint}")
        await conn.execute("""
            INSERT INTO raw_coingecko (id, fetched_at, payload)
            VALUES ($1, CURRENT_TIMESTAMP, $2::JSON)
            ON CONFLICT (id) DO UPDATE SET
                fetched_at = excluded.fetched_at,
                payload = excluded.payload;
        """, raw_id, str(data)) # Pass data as string for JSON conversion
        logger.success(f"Stored raw CoinGecko data for {coin_id}")

def parse_coingecko_market_chart(coin_id: str, raw_data: Dict[str, Any]) -> Optional[pd.DataFrame]:
    """
    Parses the CoinGecko market_chart/range response.

    Returns:
        Pandas DataFrame with 'date' and 'value' columns (price in USD), or None if parsing fails.
    """
    try:
        prices_data = raw_data.get("prices", [])
        if not prices_data:
            logger.warning(f"No 'prices' data found in CoinGecko response for {coin_id}.")
            return None

        # Data is [[timestamp_ms, price], ...]
        observations = []
        for point in prices_data:
            try:
                timestamp_ms, value = point
                if timestamp_ms is None or value is None:
                    continue

                # Convert ms timestamp to date (use UTC)
                obs_datetime_utc = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
                # Store daily price - use the date part
                obs_date = obs_datetime_utc.date()

                observations.append({"date": obs_date, "value": float(value)})

            except (ValueError, TypeError, IndexError) as e:
                logger.warning(f"Skipping CoinGecko observation due to parsing error: {e}. Raw point: {point}")
                continue

        if not observations:
            logger.warning(f"No valid observations parsed for CoinGecko coin {coin_id}.")
            return pd.DataFrame(columns=['date', 'value']) # Return empty DF

        # Group by date and take the last price for that day if multiple exist (market chart gives granular data)
        observations_df = pd.DataFrame(observations)
        # Ensure date column is datetime type for comparison if needed, though date() objects work
        # observations_df['date'] = pd.to_datetime(observations_df['date']) # If needed
        daily_prices_df = observations_df.groupby('date').last().reset_index() # Take last price for the day

        logger.success(f"Parsed {len(daily_prices_df)} daily price observations for CoinGecko coin {coin_id}.")
        return daily_prices_df

    except Exception as e:
        logger.error(f"Failed to parse CoinGecko market chart response for {coin_id}: {e}")
        return None


async def ingest_coingecko_coin_history(conn, coin_id: str, start_date: date, end_date: date):
    """Fetches, parses, and stores historical price data for a specific CoinGecko coin ID."""
    logger.info(f"Ingesting CoinGecko history for coin: {coin_id} ({start_date} to {end_date})")

    # CoinGecko uses Unix timestamps for range
    start_timestamp = int(datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc).timestamp())
    # Add one day to end_date to make the range inclusive, then get timestamp
    end_timestamp = int(datetime.combine(end_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc).timestamp())

    endpoint = f"coins/{coin_id}/market_chart/range"
    params = {
        "vs_currency": "usd", # Get prices in USD
        "from": str(start_timestamp),
        "to": str(end_timestamp)
    }

    # Fetch data
    raw_data = await fetch_coingecko_data(endpoint, params=params)
    if not raw_data:
        logger.error(f"Failed to fetch data for CoinGecko coin: {coin_id}")
        return False

    # Store raw data
    await store_raw_coingecko_data(conn, coin_id, "market_chart_range", raw_data)

    # Parse data
    observations_df = parse_coingecko_market_chart(coin_id, raw_data)
    if observations_df is None: # Parsing failed
        logger.error(f"Failed to parse data for CoinGecko coin: {coin_id}")
        return False
    elif observations_df.empty:
         logger.warning(f"No observations parsed for CoinGecko coin {coin_id}. Nothing to store.")
         return True # Not a failure if parsing worked but yielded no data

    # --- Store Observations in commodity_prices ---
    units = "usd" # Price is in USD
    source = "coingecko"
    commodity_code = coin_id # Use coin_id as the commodity code

    rows_to_insert = [
        (commodity_code, row['date'], row['value'], source, units)
        for _, row in observations_df.iterrows() if pd.notna(row['value'])
    ]

    if not rows_to_insert:
        logger.warning(f"No valid (non-null) observations to insert for {coin_id}.")
        return True

    try:
        await conn.executemany("""
            INSERT INTO commodity_prices (commodity_code, date, price, source, units, fetched_at)
            VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP)
            ON CONFLICT (commodity_code, date, source) DO UPDATE SET
                price = excluded.price,
                units = excluded.units,
                fetched_at = excluded.fetched_at;
        """, rows_to_insert)
        logger.success(f"Successfully inserted/updated {len(rows_to_insert)} prices for CoinGecko coin: {coin_id}")
        return True
    except Exception as e:
        logger.error(f"Database error inserting CoinGecko prices for {coin_id}: {e}")
        return False

async def run_coingecko_ingestion(coin_ids: List[str], days_back: int = 90):
    """
    Ingests historical price data for a list of CoinGecko coin IDs for the specified number of days back.
    Note: Free API provides daily data for ranges <= 90 days, hourly for 1-90 days, minutely for 1 day.
          Fetching daily data for longer periods might require multiple calls or a paid plan.
          This implementation fetches daily data for up to `days_back` days.
    """
    if days_back <= 0:
         logger.error("days_back must be positive for CoinGecko ingestion.")
         return

    logger.info(f"Starting CoinGecko ingestion for {len(coin_ids)} coins ({days_back} days back)...")
    conn = None
    try:
        conn = await get_db_connection()
        results = {}
        # Define date range
        end_date_obj = date.today()
        start_date_obj = end_date_obj - timedelta(days=days_back)

        for i, coin_id in enumerate(coin_ids):
            logger.info(f"Processing CoinGecko coin {i+1}/{len(coin_ids)}: {coin_id}")
            # Rate limits are strict, ensure sufficient delay handled within fetch_coingecko_data
            success = await ingest_coingecko_coin_history(conn, coin_id, start_date_obj, end_date_obj)
            results[coin_id] = success
            # Add extra safety delay if needed, though fetch has internal delays/retries
            # await asyncio.sleep(1)

        # Log summary
        successful_ids = [cid for cid, ok in results.items() if ok]
        failed_ids = [cid for cid, ok in results.items() if not ok]
        if successful_ids:
            logger.success(f"Successfully ingested CoinGecko data for: {', '.join(successful_ids)}")
        if failed_ids:
            logger.error(f"Failed to ingest CoinGecko data for: {', '.join(failed_ids)}")

    except Exception as e:
        logger.error(f"General error during CoinGecko ingestion: {e}")
    finally:
        if conn:
            await conn.close()
            logger.info("Database connection closed for CoinGecko ingest.")

# Example usage (optional):
# if __name__ == "__main__":
#     async def main():
#         # Example: Bitcoin, Ethereum, Solana prices for last 30 days
#         test_ids = ["bitcoin", "ethereum", "solana"]
#         await run_coingecko_ingestion(test_ids, days_back=30)
#     asyncio.run(main())

```

I'll wait for confirmation that `wealtharc-turbo-er/wa/ingest/coingecko.py` was created successfully. Then, I'll update the Streamlit app.
