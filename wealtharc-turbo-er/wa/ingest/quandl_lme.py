import asyncio
import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date, timezone
import pandas as pd

from wa.config import settings
from wa.db import get_db_connection

# Base URL for Quandl API v3
QUANDL_BASE_URL = "https://data.nasdaq.com/api/v3" # Quandl is now Nasdaq Data Link

@retry(stop=stop_after_attempt(3), wait=wait_fixed(3))
async def fetch_quandl_dataset_data(dataset_code: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Fetches data for a specific dataset from the Quandl (Nasdaq Data Link) API.

    Args:
        dataset_code: The Quandl dataset code (e.g., 'LME/PR_AL').
        start_date: Optional start date (YYYY-MM-DD).
        end_date: Optional end date (YYYY-MM-DD).

    Returns:
        The parsed JSON response containing dataset data, or None if an error occurs.
    """
    if not settings.QUANDL_API_KEY:
        logger.warning("QUANDL_API_KEY not set. Skipping Quandl fetch.")
        return None

    # URL format: /datasets/{database_code}/{dataset_code}/data.json
    url = f"{QUANDL_BASE_URL}/datasets/{dataset_code}/data.json"

    params = {"api_key": settings.QUANDL_API_KEY}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    # Request descending order to get latest first if needed, though default might be ascending
    # params["order"] = "desc"

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            logger.info(f"Fetching data from Quandl: {url} with params: {params}")
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            # Check for API errors within the response structure
            if "quandl_error" in data:
                qe = data["quandl_error"]
                logger.error(f"Quandl API Error ({qe.get('code')}): {qe.get('message')}")
                return None
            if "dataset_data" not in data:
                 logger.error(f"Unexpected Quandl API response structure for {dataset_code}. Missing 'dataset_data'. Response: {str(data)[:500]}...")
                 return None


            logger.success(f"Successfully fetched data from Quandl for dataset: {dataset_code}")
            return data

        except httpx.HTTPStatusError as e:
            error_details = e.response.text
            try:
                 # Try to parse JSON error if possible
                 error_json = e.response.json()
                 if "quandl_error" in error_json:
                     qe = error_json["quandl_error"]
                     error_details = f"({qe.get('code')}): {qe.get('message')}"
            except Exception:
                 pass # Ignore if not JSON
            logger.error(f"HTTP error fetching {url}: {e.response.status_code} - {error_details}")
            raise
        except Exception as e:
            logger.error(f"Error fetching data from {url}: {e}")
            raise

async def store_raw_quandl_lme_data(conn, dataset_code: str, data: Any):
    """Stores the raw Quandl LME data response."""
    if data:
        raw_id = f"quandl_{dataset_code.replace('/', '_')}" # Use dataset code in ID
        logger.debug(f"Storing raw Quandl LME data for {dataset_code}")
        await conn.execute("""
            INSERT INTO raw_quandl_lme (id, fetched_at, payload)
            VALUES ($1, CURRENT_TIMESTAMP, $2::JSON)
            ON CONFLICT (id) DO UPDATE SET
                fetched_at = excluded.fetched_at,
                payload = excluded.payload;
        """, raw_id, str(data)) # Pass data as string for JSON conversion
        logger.success(f"Stored raw Quandl LME data for {dataset_code}")

def parse_quandl_data(dataset_code: str, raw_data: Dict[str, Any]) -> Optional[pd.DataFrame]:
    """
    Parses the Quandl dataset data response.

    Returns:
        Pandas DataFrame with 'date' and 'value' columns, or None if parsing fails.
        Note: Assumes the relevant price is the second column ('Cash Buyer' for LME prices).
              This might need adjustment for other datasets.
    """
    try:
        dataset_data = raw_data.get("dataset_data", {})
        column_names = dataset_data.get("column_names", [])
        data_points = dataset_data.get("data", [])

        if not column_names or not data_points:
            logger.warning(f"No 'column_names' or 'data' found in Quandl response for {dataset_code}.")
            return None

        # Find the index of the 'Date' column and the price column
        try:
            date_index = column_names.index("Date")
        except ValueError:
            logger.error(f"'Date' column not found in Quandl response columns for {dataset_code}: {column_names}")
            return None

        # Assume the price is the second column for LME (often 'Cash Buyer' or similar)
        # This is a fragile assumption, might need smarter logic or explicit column names per dataset
        price_index = 1
        if len(column_names) <= price_index:
             logger.error(f"Expected at least {price_index + 1} columns, but got {len(column_names)} for {dataset_code}: {column_names}")
             return None
        price_column_name = column_names[price_index]
        logger.info(f"Using column '{price_column_name}' (index {price_index}) as the price for {dataset_code}.")


        # --- Extract Observations ---
        observations = []
        for point in data_points:
            try:
                if len(point) <= max(date_index, price_index):
                     logger.warning(f"Skipping row, not enough columns: {point}")
                     continue

                date_str = point[date_index]
                value = point[price_index]

                if date_str is None or value is None:
                    continue # Skip points missing essential info

                obs_date = date.fromisoformat(date_str)
                observations.append({"date": obs_date, "value": float(value)})

            except (ValueError, TypeError, IndexError) as e:
                logger.warning(f"Skipping Quandl observation due to parsing error: {e}. Raw point: {point}")
                continue

        if not observations:
            logger.warning(f"No valid observations parsed for Quandl dataset {dataset_code}.")
            return pd.DataFrame(columns=['date', 'value']) # Return empty DF

        observations_df = pd.DataFrame(observations).sort_values(by="date").reset_index(drop=True)
        logger.success(f"Parsed {len(observations_df)} observations for Quandl dataset {dataset_code}.")
        return observations_df

    except Exception as e:
        logger.error(f"Failed to parse Quandl API response structure for {dataset_code}: {e}")
        return None


async def ingest_quandl_lme_dataset(conn, dataset_code: str, start_date: Optional[str] = None, end_date: Optional[str] = None):
    """Fetches, parses, and stores data for a specific Quandl LME dataset."""
    logger.info(f"Ingesting Quandl LME dataset: {dataset_code}")

    # Fetch data first
    raw_data = await fetch_quandl_dataset_data(dataset_code, start_date, end_date)
    if not raw_data:
        logger.error(f"Failed to fetch data for Quandl dataset: {dataset_code}")
        return False

    # Store raw data
    await store_raw_quandl_lme_data(conn, dataset_code, raw_data)

    # Parse data
    observations_df = parse_quandl_data(dataset_code, raw_data)
    if observations_df is None: # Check for None, parsing might fail
        logger.error(f"Failed to parse data for Quandl dataset: {dataset_code}")
        return False
    elif observations_df.empty:
         logger.warning(f"No observations parsed for Quandl dataset {dataset_code}. Nothing to store.")
         return True # Not a failure if parsing worked but yielded no data


    # --- Store Observations in commodity_prices ---
    # Extract units if possible (might require another API call or hardcoding)
    # For now, leave units as NULL
    units = None # Placeholder
    source = "quandl_lme"

    rows_to_insert = [
        (dataset_code, row['date'], row['value'], source, units)
        for _, row in observations_df.iterrows() if pd.notna(row['value'])
    ]

    if not rows_to_insert:
        logger.warning(f"No valid (non-null) observations to insert for {dataset_code}.")
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
        logger.success(f"Successfully inserted/updated {len(rows_to_insert)} prices for Quandl dataset: {dataset_code}")
        return True
    except Exception as e:
        logger.error(f"Database error inserting Quandl prices for {dataset_code}: {e}")
        return False

async def run_quandl_lme_ingestion(dataset_codes: List[str], start_date: Optional[str] = None, end_date: Optional[str] = None):
    """Ingests data for a list of Quandl LME dataset codes."""
    logger.info(f"Starting Quandl LME ingestion for {len(dataset_codes)} datasets...")
    conn = None
    try:
        conn = await get_db_connection()
        results = {}
        for i, dataset_code in enumerate(dataset_codes):
            logger.info(f"Processing Quandl LME dataset {i+1}/{len(dataset_codes)}: {dataset_code}")
            # Add delay between requests
            await asyncio.sleep(0.5) # Small delay
            success = await ingest_quandl_lme_dataset(conn, dataset_code, start_date, end_date)
            results[dataset_code] = success

        # Log summary
        successful_codes = [code for code, ok in results.items() if ok]
        failed_codes = [code for code, ok in results.items() if not ok]
        if successful_codes:
            logger.success(f"Successfully ingested Quandl LME data for: {', '.join(successful_codes)}")
        if failed_codes:
            logger.error(f"Failed to ingest Quandl LME data for: {', '.join(failed_codes)}")

    except Exception as e:
        logger.error(f"General error during Quandl LME ingestion: {e}")
    finally:
        if conn:
            await conn.close()
            logger.info("Database connection closed for Quandl LME ingest.")

# Example usage (optional):
# if __name__ == "__main__":
#     async def main():
#         # Example: LME Aluminium, Copper, Zinc cash buyer prices
#         test_codes = ["LME/PR_AL", "LME/PR_CU", "LME/PR_ZI"]
#         await run_quandl_lme_ingestion(test_codes, start_date="2023-01-01")
#     asyncio.run(main())
```

I'll wait for confirmation that `wealtharc-turbo-er/wa/ingest/quandl_lme.py` was created successfully. Then, I'll update the Streamlit app.
