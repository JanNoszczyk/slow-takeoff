import asyncio
import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed, wait_random_exponential
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date, timezone
import pandas as pd

# Reuse the SDMX parser if sufficiently general, or copy/adapt here
# Assuming ecb_sdw.py has a suitable parser, otherwise define one here.
# For simplicity, let's copy and adapt the parsing logic here.
# from .ecb_sdw import parse_sdmx_json # If reusing

from wa.config import settings # No API key needed for public IMF data
from wa.db import get_db_connection

# Base URL for IMF SDMX JSON API
IMF_BASE_URL = "http://dataservices.imf.org/REST/SDMX_JSON.svc"

@retry(
    stop=stop_after_attempt(4),
    wait=wait_random_exponential(multiplier=1, min=3, max=15), # Wait a bit longer
    retry_error_callback=lambda retry_state: logger.warning(f"Retrying IMF fetch after error: {retry_state.outcome.exception()}")
)
async def fetch_imf_data(dataset_id: str, query_filter: str, start_year: Optional[int] = None, end_year: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    Fetches data for a specific dataset and query from the IMF SDMX-JSON API.

    Args:
        dataset_id: The IMF dataset ID (e.g., 'IFS' for International Financial Statistics).
        query_filter: The filter defining the series (e.g., 'Q.US.PMP_IX' for Quarterly US Import Price Index).
                      Format: {freq}.{area}.{indicator}[.{subindicators}]
        start_year: Optional start year.
        end_year: Optional end year.

    Returns:
        The parsed JSON response, or None if an error occurs.
    """
    # Endpoint for compact data: CompactData/{DataSetID}/{QueryFilter}
    url_path = f"/CompactData/{dataset_id}/{query_filter}"
    url = f"{IMF_BASE_URL}{url_path}"

    params = {}
    if start_year:
        params["startPeriod"] = str(start_year)
    if end_year:
        params["endPeriod"] = str(end_year)

    # No specific headers usually needed beyond standard HTTP
    headers = {"Accept": "application/json"} # Prefer standard JSON

    async with httpx.AsyncClient(timeout=120.0) as client: # Long timeout for potentially large datasets
        try:
            logger.info(f"Fetching data from IMF: {url} with params: {params}")
            response = await client.get(url, params=params, headers=headers, follow_redirects=True)
            response.raise_for_status()
            data = response.json()

            # Check for IMF specific errors (structure might vary)
            # Often errors might result in non-JSON responses or specific messages
            # This basic check assumes a successful response contains 'CompactData'
            if 'CompactData' not in data:
                 logger.error(f"Unexpected IMF API response structure for {dataset_id}/{query_filter}. Missing 'CompactData'. Response: {str(data)[:500]}...")
                 return None

            logger.success(f"Successfully fetched data from IMF for: {dataset_id}/{query_filter}")
            return data

        except httpx.HTTPStatusError as e:
            error_details = e.response.text
            # Attempt to improve logging for IMF errors if possible
            logger.error(f"HTTP error fetching {url}: {e.response.status_code} - {error_details[:500]}")
            raise
        except Exception as e:
            logger.error(f"Error fetching data from {url}: {e}")
            raise

async def store_raw_imf_data(conn, series_key: str, data: Any):
    """Stores the raw IMF SDMX-JSON data."""
    # series_key here is combination like 'IFS/Q.US.PMP_IX'
    if data:
        raw_id = f"imf_{series_key.replace('/', '_').replace('.', '_')}"
        logger.debug(f"Storing raw IMF data for {series_key}")
        await conn.execute("""
            INSERT INTO raw_imf (id, fetched_at, payload)
            VALUES ($1, CURRENT_TIMESTAMP, $2::JSON)
            ON CONFLICT (id) DO UPDATE SET
                fetched_at = excluded.fetched_at,
                payload = excluded.payload;
        """, raw_id, str(data)) # Store as JSON string
        logger.success(f"Stored raw IMF data for {series_key}")


# --- SDMX Parser (Adapted from ECB version) ---
def parse_imf_sdmx_json(series_key: str, sdmx_data: Dict[str, Any]) -> Optional[Tuple[Dict[str, str], pd.DataFrame]]:
    """
    Parses IMF SDMX-JSON CompactData structure to extract metadata and observations.

    Args:
        series_key: The identifier used for fetching (e.g., 'IFS/Q.US.PMP_IX').
        sdmx_data: The raw JSON dictionary from the IMF API.

    Returns:
        A tuple containing:
        - metadata: Dictionary of series attributes.
        - observations_df: Pandas DataFrame with 'date' and 'value' columns.
        Returns None if parsing fails.
    """
    try:
        logger.debug(f"Parsing IMF SDMX-JSON response for {series_key}...")
        compact_data = sdmx_data.get("CompactData", {})
        structure = compact_data.get("structure", {})
        dataset = compact_data.get("DataSet", {})
        series_data = dataset.get("Series", {}) # Can be dict or list of dicts

        if not structure or not dataset:
            logger.warning("IMF SDMX-JSON missing 'structure' or 'DataSet'.")
            return None

        # If 'Series' is a list, process the first one (assuming single series query)
        if isinstance(series_data, list):
            if not series_data:
                logger.warning("IMF SDMX-JSON 'Series' list is empty.")
                return None
            series_info = series_data[0]
        else:
            series_info = series_data # Assume it's a dict for a single series

        # --- Extract Metadata (Series Attributes) ---
        series_attributes = {}
        attributes = structure.get("attributes", {}).get("Series", []) # Note: Capital 'S'
        attribute_values = series_info.get("@OBS_STATUS", []) # Placeholder, need real attr names

        # Dimensions provide key info
        dimensions = structure.get("dimensions", {}).get("Series", []) # Note: Capital 'S'
        key_values = {dim.get("id"): series_info.get(f"@{dim.get('id')}") for dim in dimensions}

        # Get coded values from Dimension descriptions
        dim_value_map = {}
        if "CodeLists" in structure: # Adjust based on actual structure name
             codelists = {cl['id']: cl['Code'] for cl in structure['CodeLists']} # Example structure
             for dim_id, dim_value_code in key_values.items():
                  if dim_id in codelists:
                       value_name = next((code['description'] for code in codelists[dim_id] if code['id'] == dim_value_code), dim_value_code)
                       dim_value_map[dim_id] = value_name
                  else:
                       dim_value_map[dim_id] = dim_value_code # Fallback to code


        series_attributes.update(dim_value_map) # Add resolved dimension values
        series_attributes['SOURCE_KEY'] = series_key # Store the original key

        # Try to find a title/name - structure varies wildly
        name = series_key # Default name
        if 'INDICATOR' in series_attributes: name = f"{series_attributes.get('AREA', '')} - {series_attributes['INDICATOR']}"
        series_attributes['CALCULATED_NAME'] = name

        logger.debug(f"Extracted IMF series attributes: {series_attributes}")

        # --- Extract Observations ---
        obs_list = []
        observations = series_info.get("Obs", []) # List of observations
        if not isinstance(observations, list): # Handle case where single obs might not be list
            observations = [observations] if observations else []

        for obs_data in observations:
            try:
                # Time period and value keys might be like '@TIME_PERIOD', '@OBS_VALUE'
                time_str = obs_data.get("@TIME_PERIOD")
                value_str = obs_data.get("@OBS_VALUE")

                if time_str is None or value_str is None:
                    continue

                # Parse time period (e.g., '2023', '2023-Q1', '2023-M1')
                obs_date: Optional[date] = None
                if len(time_str) == 4: # Annual YYYY
                    obs_date = date(int(time_str), 12, 31)
                elif '-Q' in time_str and len(time_str) == 7: # Quarterly YYYY-Qx
                     year, quarter_str = time_str.split('-Q')
                     quarter_end_month = int(quarter_str) * 3
                     next_month_start = date(int(year), quarter_end_month, 1).replace(day=28) + pd.Timedelta(days=4)
                     obs_date = next_month_start - pd.Timedelta(days=next_month_start.day)
                elif '-M' in time_str and len(time_str) == 7: # Monthly YYYY-Mx
                     year, month_str = time_str.split('-M')
                     month = int(month_str)
                     next_month_start = date(int(year), month, 1).replace(day=28) + pd.Timedelta(days=4)
                     obs_date = next_month_start - pd.Timedelta(days=next_month_start.day)
                elif time_str.count('-') == 2 and len(time_str) == 10: # Daily YYYY-MM-DD (less common in IMF?)
                     obs_date = date.fromisoformat(time_str)
                else:
                     logger.warning(f"Unrecognized IMF time format: {time_str}")
                     continue

                value = float(value_str)
                obs_list.append({"date": obs_date, "value": value})

            except (ValueError, TypeError, KeyError) as e:
                logger.warning(f"Skipping IMF observation due to parsing error: {e}. Raw obs: {obs_data}")
                continue

        if not obs_list:
            logger.warning("No valid IMF observations parsed.")
            return series_attributes, pd.DataFrame(columns=['date', 'value'])

        observations_df = pd.DataFrame(obs_list).sort_values(by="date").reset_index(drop=True)
        logger.success(f"Parsed {len(observations_df)} observations for IMF series {series_key}.")
        return series_attributes, observations_df

    except Exception as e:
        logger.error(f"Failed to parse IMF SDMX-JSON structure for {series_key}: {e}")
        return None

async def ingest_imf_series(conn, dataset_id: str, query_filter: str, start_year: Optional[int] = None, end_year: Optional[int] = None):
    """Fetches, parses, and stores data for a specific IMF series."""
    series_key = f"{dataset_id}/{query_filter}" # Combine for unique ID
    logger.info(f"Ingesting IMF series: {series_key}")

    # Fetch data
    raw_data = await fetch_imf_data(dataset_id, query_filter, start_year, end_year)
    if not raw_data:
        logger.error(f"Failed to fetch data for IMF series: {series_key}")
        return False

    # Store raw data
    await store_raw_imf_data(conn, series_key, raw_data)

    # Parse data
    parsed_result = parse_imf_sdmx_json(series_key, raw_data)
    if not parsed_result:
        logger.error(f"Failed to parse data for IMF series: {series_key}")
        return False

    metadata, observations_df = parsed_result

    # --- Store Metadata in macro_series ---
    try:
        # Use query_filter or a combination as series_id in DB
        db_series_id = f"IMF_{query_filter.replace('.', '_')}"
        name = metadata.get("CALCULATED_NAME", db_series_id)
        frequency = metadata.get("FREQ", "Unknown") # Extract frequency if available
        units = metadata.get("UNIT_MULT") # Or other relevant unit attribute
        source = "imf"

        logger.info(f"Updating metadata for {db_series_id}: Name='{name}', Freq='{frequency}', Units='{units}'")
        await conn.execute("""
            INSERT INTO macro_series (series_id, name, frequency, units, source)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (series_id) DO UPDATE SET
                name = excluded.name,
                frequency = excluded.frequency,
                units = excluded.units,
                source = excluded.source;
        """, db_series_id, name, frequency, units, source)
        logger.success(f"Successfully updated metadata for IMF series: {db_series_id}")
    except Exception as e:
        logger.error(f"Error storing IMF series metadata for {db_series_id}: {e}\nMetadata: {metadata}")
        # Continue?

    # --- Store Observations in macro_data ---
    if observations_df.empty:
        logger.warning(f"No valid observations to store for IMF series: {db_series_id}")
        return True

    rows_to_insert = [
        (db_series_id, row['date'], row['value'])
        for _, row in observations_df.iterrows() if pd.notna(row['value'])
    ]

    if not rows_to_insert:
        logger.warning(f"No valid (non-null) observations to insert for {db_series_id}.")
        return True

    try:
        await conn.executemany("""
            INSERT INTO macro_data (series_id, date, value, fetched_at)
            VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
            ON CONFLICT (series_id, date) DO UPDATE SET
                value = excluded.value,
                fetched_at = excluded.fetched_at;
        """, rows_to_insert)
        logger.success(f"Successfully inserted/updated {len(rows_to_insert)} observations for IMF series: {db_series_id}")
        return True
    except Exception as e:
        logger.error(f"Database error inserting IMF observations for {db_series_id}: {e}")
        return False

async def run_imf_ingestion(series_list: List[Tuple[str, str]], start_year: Optional[int] = None, end_year: Optional[int] = None):
    """
    Ingests data for a list of IMF series.

    Args:
        series_list: List of tuples, each containing (dataset_id, query_filter).
                     Example: [('IFS', 'Q.US.PMP_IX'), ('IFS', 'Q.GB.PMP_IX')]
        start_year: Optional start year.
        end_year: Optional end year.
    """
    logger.info(f"Starting IMF ingestion for {len(series_list)} series...")
    conn = None
    try:
        conn = await get_db_connection()
        results = {}
        for i, (dataset_id, query_filter) in enumerate(series_list):
            series_key = f"{dataset_id}/{query_filter}"
            logger.info(f"Processing IMF series {i+1}/{len(series_list)}: {series_key}")
            # Add delay
            await asyncio.sleep(1)
            success = await ingest_imf_series(conn, dataset_id, query_filter, start_year, end_year)
            results[series_key] = success

        # Log summary
        successful_keys = [key for key, ok in results.items() if ok]
        failed_keys = [key for key, ok in results.items() if not ok]
        if successful_keys:
            logger.success(f"Successfully ingested IMF data for: {', '.join(successful_keys)}")
        if failed_keys:
            logger.error(f"Failed to ingest IMF data for: {', '.join(failed_keys)}")

    except Exception as e:
        logger.error(f"General error during IMF ingestion: {e}")
    finally:
        if conn:
            await conn.close()
            logger.info("Database connection closed for IMF ingest.")

# Example usage (optional):
# if __name__ == "__main__":
#     async def main():
#         # Example: Quarterly Import Price Index for US and GB from IFS dataset
#         test_series = [
#             ('IFS', 'Q.US.PMP_IX'),
#             ('IFS', 'Q.GB.PMP_IX')
#         ]
#         await run_imf_ingestion(test_series, start_year=2020)
#     asyncio.run(main())

```

I'll wait for confirmation that `wealtharc-turbo-er/wa/ingest/imf.py` was created successfully. Then, I'll update the Streamlit app.
