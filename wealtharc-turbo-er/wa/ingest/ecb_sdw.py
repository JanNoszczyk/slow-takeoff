import asyncio
import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date
import pandas as pd # Useful for parsing SDMX structure

from wa.config import settings # No specific API key needed for public SDW data
from wa.db import get_db_connection

# Base URL for ECB SDW REST API
ECB_SDW_BASE_URL = "https://data-api.ecb.europa.eu/service"

@retry(stop=stop_after_attempt(3), wait=wait_fixed(5)) # Wait longer, ECB API can be slower
async def fetch_ecb_sdw_data(resource: str = "data", flow_ref: str = "EXR", key: str = "D.USD.EUR.SP00.A", params: Optional[Dict[str, Any]] = None) -> Any:
    """
    Fetches data from the ECB Statistical Data Warehouse API using SDMX-JSON.

    Args:
        resource: The API resource (default 'data'). Others include 'datastructure'.
        flow_ref: The dataflow reference (e.g., 'EXR' for exchange rates).
        key: The key identifying the specific series (e.g., 'D.USD.EUR.SP00.A' for Daily USD/EUR spot rate).
             Format varies by dataflow. Use ECB SDW website to find keys.
        params: Additional query parameters (e.g., startPeriod, endPeriod). Format: YYYY-MM-DD or YYYY.

    Returns:
        The parsed JSON response, or None if an error occurs.
    """
    # Construct URL: /service/{resource}/{flowRef}/{key}
    url = f"{ECB_SDW_BASE_URL}/{resource}/{flow_ref}/{key}"

    # Standard headers for SDMX-JSON
    headers = {"Accept": "application/vnd.sdmx.data+json;version=1.0.0-wd"}

    # Default params if none provided, can add start/end period here
    query_params = params if params is not None else {}
    # Example: query_params = {"startPeriod": "2023-01-01", "endPeriod": "2023-12-31"}

    async with httpx.AsyncClient(timeout=90.0) as client: # Increase timeout significantly
        try:
            logger.info(f"Fetching data from ECB SDW: {url} with params: {query_params}")
            response = await client.get(url, params=query_params, headers=headers)
            response.raise_for_status()
            data = response.json()
            logger.success(f"Successfully fetched data from ECB SDW for key: {key}")
            return data
        except httpx.HTTPStatusError as e:
            # Log more details from ECB errors if possible
            error_details = e.response.text
            try:
                error_json = e.response.json()
                error_details = error_json.get("error", {}).get("message", error_details)
            except Exception:
                pass # Ignore if response is not JSON
            logger.error(f"HTTP error fetching {url}: {e.response.status_code} - {error_details}")
            raise
        except Exception as e:
            logger.error(f"Error fetching data from {url}: {e}")
            raise

async def store_raw_ecb_data(conn, series_key: str, data: Any):
    """Stores the raw SDMX-JSON data from ECB SDW."""
    if data:
        raw_id = f"ecb_sdw_{series_key}"
        logger.debug(f"Storing raw ECB SDW data for {series_key}")
        await conn.execute("""
            INSERT INTO raw_ecb_sdw (id, fetched_at, payload)
            VALUES ($1, CURRENT_TIMESTAMP, $2::JSON)
            ON CONFLICT (id) DO UPDATE SET
                fetched_at = excluded.fetched_at,
                payload = excluded.payload;
        """, raw_id, str(data)) # Pass data as string for JSON conversion
        logger.success(f"Stored raw ECB SDW data for {series_key}")


def parse_sdmx_json(sdmx_data: Dict[str, Any]) -> Optional[Tuple[Dict[str, str], pd.DataFrame]]:
    """
    Parses SDMX-JSON data structure to extract metadata and observations.

    Returns:
        A tuple containing:
        - metadata: Dictionary of series attributes (e.g., TITLE, DECIMALS).
        - observations_df: Pandas DataFrame with 'date' and 'value' columns.
        Returns None if parsing fails.
    """
    try:
        logger.debug("Parsing SDMX-JSON response...")
        structure = sdmx_data.get("structure", {})
        data_sets = sdmx_data.get("dataSets", [])
        if not structure or not data_sets:
            logger.warning("SDMX-JSON missing 'structure' or 'dataSets'.")
            return None

        # --- Extract Metadata (Series Attributes) ---
        series_attributes = {}
        attributes = structure.get("attributes", {}).get("series", [])
        series_data = data_sets[0].get("series", {})
        # SDMX structure can be complex, assuming '0:0:0:0:0' key format is common, might need adjustment
        series_key_index = next(iter(series_data), None) # Get the first series key like '0:0:0:0:0'
        if series_key_index is None:
             logger.warning("Could not find series key index (e.g., '0:0:0:0:0') in dataSets.")
             return None

        series_info = series_data.get(series_key_index, {})
        attribute_values = series_info.get("attributes", [])

        # Map attribute values back to names using their index position
        for i, attr_def in enumerate(attributes):
            attr_id = attr_def.get("id")
            attr_name = attr_def.get("name", attr_id) # Use name, fallback to ID
            if i < len(attribute_values) and attribute_values[i] is not None:
                 # The actual value is often nested within 'values' list
                 value_index = attribute_values[i]
                 value_list = attr_def.get("values", [])
                 if value_index < len(value_list):
                     series_attributes[attr_id] = value_list[value_index].get("name", value_list[value_index].get("id"))
                 else:
                     # Sometimes the value index IS the value (if no 'values' list) - needs verification
                     series_attributes[attr_id] = value_index # Fallback assumption

        # Also try to get the main dimension names/values
        dimensions = structure.get("dimensions", {}).get("observation", [])
        dimension_values = structure.get("dimensions", {}).get("series", [])
        key_parts = series_key_index.split(':')
        for i, dim_def in enumerate(dimension_values):
            dim_id = dim_def.get("id")
            if i < len(key_parts):
                 value_index = int(key_parts[i])
                 value_list = dim_def.get("values", [])
                 if value_index < len(value_list):
                      series_attributes[dim_id] = value_list[value_index].get("name", value_list[value_index].get("id"))


        logger.debug(f"Extracted series attributes: {series_attributes}")

        # --- Extract Observations ---
        obs_list = []
        observations = series_info.get("observations", {})
        # Time period dimension is usually the last one in observation dimensions
        time_dim_index = -1
        for i, dim in enumerate(dimensions):
            if dim.get("role") == "time":
                time_dim_index = i
                break
        if time_dim_index == -1:
             # Fallback: assume time is the first dimension if role not set
             time_dim_index = 0
             logger.warning("Time dimension role not found, assuming index 0.")

        time_values = dimensions[time_dim_index].get("values", [])

        for obs_key, obs_data in observations.items():
            try:
                # Key often corresponds to the index in the time dimension values
                time_index = int(obs_key)
                if time_index < len(time_values):
                    date_str = time_values[time_index].get("id") # Use ID which is typically YYYY-MM-DD or YYYY
                    # Parse date string - handle different formats if necessary
                    if '-' in date_str and len(date_str) >= 10:
                        obs_date = date.fromisoformat(date_str[:10])
                    elif len(date_str) == 4: # Handle annual data YYYY
                        obs_date = date(int(date_str), 12, 31) # Use year end? Or start? End is safer.
                    else:
                         logger.warning(f"Unrecognized date format: {date_str}")
                         continue

                    # Observation value is usually the first element in the list
                    value = obs_data[0]
                    if value is not None: # Null values might be present
                        obs_list.append({"date": obs_date, "value": float(value)})

                else:
                    logger.warning(f"Observation key {obs_key} out of range for time dimension.")

            except (ValueError, TypeError, IndexError) as e:
                logger.warning(f"Skipping observation due to parsing error: {e}. Raw obs: {obs_key}: {obs_data}")
                continue

        if not obs_list:
            logger.warning("No valid observations parsed.")
            # Return metadata even if observations are empty/failed
            return series_attributes, pd.DataFrame(columns=['date', 'value'])


        observations_df = pd.DataFrame(obs_list).sort_values(by="date").reset_index(drop=True)
        logger.success(f"Parsed {len(observations_df)} observations.")
        return series_attributes, observations_df

    except Exception as e:
        logger.error(f"Failed to parse SDMX-JSON structure: {e}")
        return None


async def ingest_ecb_sdw_series(conn, flow_ref: str, series_key: str, start_date: str = None, end_date: str = None):
    """Fetches, parses, and stores data for a specific ECB SDW series."""
    logger.info(f"Ingesting ECB SDW series: Flow={flow_ref}, Key={series_key}")

    params = {}
    if start_date:
        params["startPeriod"] = start_date
    if end_date:
        params["endPeriod"] = end_date

    sdmx_data = await fetch_ecb_sdw_data(flow_ref=flow_ref, key=series_key, params=params)

    if not sdmx_data:
        logger.error(f"Failed to fetch data for ECB series: {series_key}")
        return False

    await store_raw_ecb_data(conn, series_key, sdmx_data)

    parsed_result = parse_sdmx_json(sdmx_data)
    if not parsed_result:
        logger.error(f"Failed to parse SDMX-JSON for ECB series: {series_key}")
        return False

    metadata, observations_df = parsed_result

    # --- Store Metadata ---
    try:
        # Extract relevant fields - adjust based on typical ECB metadata names
        # Often 'TITLE' is the main name. Frequency might be in dimensions.
        name = metadata.get("TITLE", series_key) # Fallback to key if no title
        freq_code = metadata.get("FREQ") # e.g., 'D' for Daily, 'M' for Monthly
        frequency_map = {'A': 'Annual', 'Q': 'Quarterly', 'M': 'Monthly', 'W': 'Weekly', 'D': 'Daily'}
        frequency = frequency_map.get(freq_code, freq_code) # Map code or keep code
        units = metadata.get("UNIT_MEASURE", metadata.get("UNIT"))

        logger.info(f"Updating metadata for {series_key}: Name='{name}', Freq='{frequency}', Units='{units}'")
        await conn.execute("""
            INSERT INTO macro_series (series_id, name, frequency, units, source)
            VALUES ($1, $2, $3, $4, 'ecb_sdw')
            ON CONFLICT (series_id) DO UPDATE SET
                name = excluded.name,
                frequency = excluded.frequency,
                units = excluded.units,
                source = excluded.source;
        """, series_key, name, frequency, units)
        logger.success(f"Successfully updated metadata for ECB series: {series_key}")
    except Exception as e:
        logger.error(f"Error storing ECB series metadata for {series_key}: {e}\nMetadata: {metadata}")
        # Continue to store observations even if metadata fails? Maybe.
        # return False

    # --- Store Observations ---
    if observations_df.empty:
        logger.warning(f"No valid observations to store for ECB series: {series_key}")
        return True # Not an error if no data points

    rows_to_insert = [
        (series_key, row['date'], row['value'])
        for _, row in observations_df.iterrows() if pd.notna(row['value']) # Ensure value is not NaN
    ]

    if not rows_to_insert:
        logger.warning(f"No valid (non-null) observations to insert for {series_key}.")
        return True

    try:
        await conn.executemany("""
            INSERT INTO macro_data (series_id, date, value, fetched_at)
            VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
            ON CONFLICT (series_id, date) DO UPDATE SET
                value = excluded.value,
                fetched_at = excluded.fetched_at;
        """, rows_to_insert)
        logger.success(f"Successfully inserted/updated {len(rows_to_insert)} observations for ECB series: {series_key}")
        return True
    except Exception as e:
        logger.error(f"Database error inserting observations for {series_key}: {e}")
        return False


async def run_ecb_sdw_ingestion(series_map: Dict[str, str], start_date: str = None, end_date: str = None):
    """
    Ingests data for multiple ECB SDW series defined in a map.

    Args:
        series_map: Dictionary where keys are flowRefs and values are lists of series keys for that flow.
                    Example: {"EXR": ["D.USD.EUR.SP00.A", "D.GBP.EUR.SP00.A"], "YC": ["B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y"]}
        start_date: Optional start date string (YYYY-MM-DD).
        end_date: Optional end date string (YYYY-MM-DD).
    """
    logger.info(f"Starting ECB SDW ingestion for {len(series_map)} flows...")
    conn = None
    try:
        conn = await get_db_connection()
        results = {}
        total_series_count = sum(len(keys) for keys in series_map.values())
        current_series_num = 0

        for flow_ref, series_keys in series_map.items():
            for series_key in series_keys:
                current_series_num += 1
                logger.info(f"Processing series {current_series_num}/{total_series_count}: {flow_ref}/{series_key}")
                # Add a small delay to be nice to the API
                await asyncio.sleep(1)
                success = await ingest_ecb_sdw_series(conn, flow_ref, series_key, start_date, end_date)
                results[f"{flow_ref}/{series_key}"] = success

        # Log summary
        successful_keys = [key for key, ok in results.items() if ok]
        failed_keys = [key for key, ok in results.items() if not ok]
        if successful_keys:
            logger.success(f"Successfully ingested ECB SDW data for: {', '.join(successful_keys)}")
        if failed_keys:
            logger.error(f"Failed to ingest ECB SDW data for: {', '.join(failed_keys)}")

    except Exception as e:
        logger.error(f"General error during ECB SDW ingestion: {e}")
    finally:
        if conn:
            await conn.close()
            logger.info("Database connection closed for ECB SDW ingest.")

# Example usage (optional):
# if __name__ == "__main__":
#     async def main():
#         # Example: Fetch daily USD/EUR rate and 10Y Euro area yield curve data for 2023
#         example_series = {
#             "EXR": ["D.USD.EUR.SP00.A", "D.GBP.EUR.SP00.A"], # Daily USD/EUR and GBP/EUR spot rates
#             "YC": ["B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y"]      # Euro area 10Y gov bond yield
#         }
#         await run_ecb_sdw_ingestion(example_series, start_date="2023-01-01", end_date="2023-12-31")
#     asyncio.run(main())
```

I'll wait for confirmation that `wealtharc-turbo-er/wa/ingest/ecb_sdw.py` was created successfully. Then, I'll update the Streamlit app to include a trigger for this ingestor.
