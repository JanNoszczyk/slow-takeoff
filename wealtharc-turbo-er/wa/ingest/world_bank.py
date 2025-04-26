import asyncio
import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed, wait_random_exponential
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date, timezone
import pandas as pd

from wa.config import settings # No API key generally needed
from wa.db import get_db_connection

# Base URL for World Bank API v2
WORLD_BANK_BASE_URL = "https://api.worldbank.org/v2"

# Note: World Bank API can have usage limits, but is generally permissive for moderate use.

@retry(
    stop=stop_after_attempt(4),
    wait=wait_random_exponential(multiplier=1, min=2, max=10),
    retry_error_callback=lambda retry_state: logger.warning(f"Retrying World Bank fetch after error: {retry_state.outcome.exception()}")
)
async def fetch_world_bank_data(
    indicator_code: str,
    country_codes: List[str] = ["all"], # Default to all countries/regions
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    per_page: int = 1000 # Fetch more per page to reduce calls
) -> Optional[List[Dict[str, Any]]]:
    """
    Fetches data for a specific indicator and countries from the World Bank API.

    Handles pagination automatically.

    Args:
        indicator_code: The World Bank indicator code (e.g., 'NY.GDP.MKTP.CD').
        country_codes: List of ISO alpha-2 country codes or 'all'. Semicolon-separated if multiple.
        start_year: Optional start year.
        end_year: Optional end year.
        per_page: Number of records per page.

    Returns:
        A list containing all data points across all pages, or None if a fatal error occurs.
    """
    # Format country codes: 'all' or 'US;CA;MX'
    countries_str = ";".join(country_codes) if country_codes != ["all"] else "all"
    url_path = f"/country/{countries_str}/indicator/{indicator_code}"
    url = f"{WORLD_BANK_BASE_URL}{url_path}"

    params = {
        "format": "json",
        "per_page": str(per_page),
    }
    if start_year and end_year:
        params["date"] = f"{start_year}:{end_year}"
    elif start_year:
        # WB API date filter isn't strictly start/end, but a range or single year.
        # Fetching from start_year to current year implicitly if end_year is None.
        params["date"] = f"{start_year}:{datetime.now().year}"
    elif end_year:
         params["date"] = str(end_year) # Fetch only specific end year if start is None


    all_data_points = []
    current_page = 1

    async with httpx.AsyncClient(timeout=90.0) as client: # Longer timeout for potentially many pages
        while True:
            params["page"] = str(current_page)
            logger.info(f"Fetching World Bank data: Indicator={indicator_code}, Countries={countries_str}, Page={current_page}")

            try:
                # Add slight delay between pages
                if current_page > 1: await asyncio.sleep(0.5)

                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                # Response structure: [{pagination_info}, [data_points...]]
                if not isinstance(data, list) or len(data) != 2:
                     # Check for error message format: [{'message': [{'id': '...', 'key': '...', 'value': '...'}]}]
                     if isinstance(data, list) and len(data) == 1 and 'message' in data[0]:
                          error_msg = data[0]['message'][0].get('value', 'Unknown World Bank API error')
                          logger.error(f"World Bank API Error: {error_msg}")
                          return None # Fatal error for this indicator fetch
                     else:
                          logger.error(f"Unexpected World Bank API response structure for {indicator_code}, page {current_page}. Response: {str(data)[:500]}...")
                          # Attempt to continue if prior pages had data? Risky. Return None for now.
                          return None

                pagination_info = data[0]
                page_data_points = data[1]

                if page_data_points: # Check if list is not None and not empty
                    all_data_points.extend(page_data_points)
                    logger.debug(f"Fetched {len(page_data_points)} data points from page {current_page}.")
                else:
                    logger.debug(f"No more data points found on page {current_page}.")
                    break # No more data on this page

                # Check if this was the last page
                total_pages = pagination_info.get("pages", 0)
                if current_page >= total_pages or total_pages == 0:
                    logger.info(f"Finished fetching all {total_pages} pages for {indicator_code}.")
                    break # Reached the last page or only one page

                current_page += 1

            except httpx.HTTPStatusError as e:
                error_details = e.response.text
                try:
                    # Check specific WB error format
                    error_json = e.response.json()
                    if isinstance(error_json, list) and len(error_json) == 1 and 'message' in error_json[0]:
                         error_details = error_json[0]['message'][0].get('value', error_details)
                except Exception:
                    pass
                logger.error(f"HTTP error fetching {url} (Page {current_page}): {e.response.status_code} - {error_details}")
                # Depending on error, might want to stop or let tenacity handle retry (if applicable to pagination)
                # For now, treat as fatal for this indicator fetch
                return None
            except Exception as e:
                logger.error(f"Error fetching data from {url} (Page {current_page}): {e}")
                # Treat as fatal for this indicator fetch
                return None

    logger.success(f"Successfully fetched {len(all_data_points)} total data points for World Bank indicator {indicator_code}")
    return all_data_points


async def store_raw_world_bank_data(conn, indicator_code: str, countries_str: str, data: List[Dict[str, Any]]):
    """Stores the raw World Bank API response (list of data points)."""
    if data:
        # Use indicator and maybe hash of countries/timestamp for ID
        timestamp_str = str(int(time.time()))
        raw_id = f"worldbank_{indicator_code}_{countries_str.replace(';','-')}_{timestamp_str}"
        logger.debug(f"Storing raw World Bank data for {indicator_code} / {countries_str}")
        await conn.execute("""
            INSERT INTO raw_world_bank (id, fetched_at, payload)
            VALUES ($1, CURRENT_TIMESTAMP, $2::JSON)
            ON CONFLICT (id) DO UPDATE SET
                fetched_at = excluded.fetched_at,
                payload = excluded.payload;
        """, raw_id, str(data)) # Store list of dicts as JSON string
        logger.success(f"Stored raw World Bank data for {indicator_code}")

def parse_world_bank_data(indicator_code: str, raw_data_list: List[Dict[str, Any]]) -> Optional[Tuple[Dict[str, Any], pd.DataFrame]]:
    """
    Parses the list of data points from World Bank API response.

    Returns:
        A tuple (metadata, observations_df), or None if parsing fails.
        Metadata will contain indicator name and units if found consistently.
        Observations DataFrame will have 'series_id', 'date', 'value'.
    """
    if not raw_data_list:
        logger.warning(f"No raw data points provided for parsing World Bank indicator {indicator_code}.")
        return None

    try:
        # --- Extract Metadata (from first data point) ---
        first_point = raw_data_list[0]
        metadata = {
            "series_id": indicator_code, # Use indicator code as the series ID
            "name": first_point.get("indicator", {}).get("value", indicator_code),
            "units": first_point.get("unit"), # Often empty string
            "frequency": "Annual", # World Bank data is typically annual
        }
        logger.debug(f"Extracted World Bank metadata for {indicator_code}: {metadata}")

        # --- Extract Observations ---
        observations = []
        for point in raw_data_list:
            try:
                value = point.get("value")
                date_str = point.get("date") # Year as string 'YYYY'
                # Use specific country + indicator as series ID? Or just indicator?
                # Sticking to indicator code for macro_series/macro_data for simplicity.
                # Could create a compound key if needed: WB_{country_iso}_{indicator_code}
                series_id_for_obs = indicator_code # Aggregate all countries under one series ID for now

                # World Bank country field can be useful for filtering later if needed
                country_name = point.get("country", {}).get("value")
                country_iso = point.get("countryiso3code")

                if value is None or not date_str: # Skip null values or missing dates
                    continue

                # Convert year string to date (use end of year)
                obs_date = date(int(date_str), 12, 31)

                observations.append({
                    "series_id": series_id_for_obs,
                    "date": obs_date,
                    "value": float(value),
                    # Add country info if needed in DF for later processing
                    "country_name": country_name,
                    "country_iso": country_iso,
                })

            except (ValueError, TypeError, KeyError) as e:
                logger.warning(f"Skipping World Bank observation due to parsing error: {e}. Raw point: {point}")
                continue

        if not observations:
            logger.warning(f"No valid observations parsed for World Bank indicator {indicator_code}.")
            return metadata, pd.DataFrame(columns=['series_id', 'date', 'value']) # Return empty DF

        observations_df = pd.DataFrame(observations)
        logger.success(f"Parsed {len(observations_df)} observations for World Bank indicator {indicator_code}.")
        # Note: This DF contains data for potentially multiple countries under the same series_id.
        # The insertion logic needs to handle this (e.g., aggregate or store country info).
        # For now, macro_data stores only series_id, date, value. We'll average/sum later if needed,
        # or adjust the DB schema. Let's store the 'World' aggregate if available, otherwise maybe US?
        # Filtering for 'World' (ISO: WLD) or a primary country like 'USA'
        world_df = observations_df[observations_df['country_iso'] == 'WLD']
        if not world_df.empty:
             logger.info("Using 'World' aggregate data.")
             final_df = world_df[['series_id', 'date', 'value']].sort_values(by="date").reset_index(drop=True)
        else:
             # Fallback to US or another major country if needed, or just take first available?
             # Taking first available country's data per year for simplicity now.
             logger.warning(f"'World' aggregate not found for {indicator_code}. Using data from first available country per year.")
             final_df = observations_df.groupby('date').first().reset_index()[['series_id', 'date', 'value']]

        return metadata, final_df

    except Exception as e:
        logger.error(f"Failed to parse World Bank API response list for {indicator_code}: {e}")
        return None


async def ingest_world_bank_indicator(conn, indicator_code: str, country_codes: List[str] = ["WLD"], start_year: Optional[int] = None, end_year: Optional[int] = None):
    """Fetches, parses, and stores data for a specific World Bank indicator."""
    logger.info(f"Ingesting World Bank indicator: {indicator_code} for countries: {country_codes}")

    # Default to World (WLD) if specific countries not requested
    countries_to_fetch = country_codes if country_codes else ["WLD"]

    # Fetch data first (handles pagination)
    raw_data_list = await fetch_world_bank_data(indicator_code, countries_to_fetch, start_year, end_year)
    if raw_data_list is None: # Check for None, fetch handles fatal errors
        logger.error(f"Failed to fetch data for World Bank indicator: {indicator_code}")
        return False

    # Store raw data (optional, but good practice)
    countries_str = ";".join(countries_to_fetch)
    await store_raw_world_bank_data(conn, indicator_code, countries_str, raw_data_list)

    # Parse data
    parsed_result = parse_world_bank_data(indicator_code, raw_data_list)
    if not parsed_result:
        logger.error(f"Failed to parse data for World Bank indicator: {indicator_code}")
        return False

    metadata, observations_df = parsed_result # observations_df should now be filtered/aggregated

    # --- Store Metadata in macro_series ---
    try:
        name = metadata.get("name", indicator_code)
        frequency = metadata.get("frequency", "Annual") # Default to Annual
        units = metadata.get("units")
        source = "world_bank"

        logger.info(f"Updating metadata for {indicator_code}: Name='{name}', Freq='{frequency}', Units='{units}'")
        await conn.execute("""
            INSERT INTO macro_series (series_id, name, frequency, units, source)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (series_id) DO UPDATE SET
                name = excluded.name,
                frequency = excluded.frequency,
                units = excluded.units,
                source = excluded.source;
        """, indicator_code, name, frequency, units, source)
        logger.success(f"Successfully updated metadata for World Bank indicator: {indicator_code}")
    except Exception as e:
        logger.error(f"Error storing World Bank indicator metadata for {indicator_code}: {e}\nMetadata: {metadata}")
        # Continue?

    # --- Store Observations in macro_data ---
    if observations_df.empty:
        logger.warning(f"No valid observations to store for World Bank indicator: {indicator_code}")
        return True # Not an error if no data points

    rows_to_insert = [
        (row['series_id'], row['date'], row['value']) # Using indicator_code as series_id
        for _, row in observations_df.iterrows() if pd.notna(row['value'])
    ]

    if not rows_to_insert:
        logger.warning(f"No valid (non-null) observations to insert for {indicator_code}.")
        return True

    try:
        await conn.executemany("""
            INSERT INTO macro_data (series_id, date, value, fetched_at)
            VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
            ON CONFLICT (series_id, date) DO UPDATE SET
                value = excluded.value,
                fetched_at = excluded.fetched_at;
        """, rows_to_insert)
        logger.success(f"Successfully inserted/updated {len(rows_to_insert)} observations for World Bank indicator: {indicator_code}")
        return True
    except Exception as e:
        logger.error(f"Database error inserting World Bank observations for {indicator_code}: {e}")
        return False

async def run_world_bank_ingestion(indicator_codes: List[str], country_codes: List[str] = ["WLD"], start_year: Optional[int] = None, end_year: Optional[int] = None):
    """Ingests data for a list of World Bank indicators."""
    logger.info(f"Starting World Bank ingestion for {len(indicator_codes)} indicators...")
    conn = None
    try:
        conn = await get_db_connection()
        results = {}
        for i, indicator_code in enumerate(indicator_codes):
            logger.info(f"Processing WB indicator {i+1}/{len(indicator_codes)}: {indicator_code}")
            # Add delay between indicators
            await asyncio.sleep(1)
            success = await ingest_world_bank_indicator(conn, indicator_code, country_codes, start_year, end_year)
            results[indicator_code] = success

        # Log summary
        successful_codes = [code for code, ok in results.items() if ok]
        failed_codes = [code for code, ok in results.items() if not ok]
        if successful_codes:
            logger.success(f"Successfully ingested World Bank data for: {', '.join(successful_codes)}")
        if failed_codes:
            logger.error(f"Failed to ingest World Bank data for: {', '.join(failed_codes)}")

    except Exception as e:
        logger.error(f"General error during World Bank ingestion: {e}")
    finally:
        if conn:
            await conn.close()
            logger.info("Database connection closed for World Bank ingest.")

# Example usage (optional):
# if __name__ == "__main__":
#     async def main():
#         # Example: World GDP (Current US$), Population Total
#         test_indicators = ["NY.GDP.MKTP.CD", "SP.POP.TOTL"]
#         await run_world_bank_ingestion(test_indicators, country_codes=["WLD"], start_year=2010) # World aggregate since 2010
#     asyncio.run(main())
```

I'll wait for confirmation that `wealtharc-turbo-er/wa/ingest/world_bank.py` was created successfully. Then, I'll update the Streamlit app.
