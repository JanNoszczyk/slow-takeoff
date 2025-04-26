# wealtharc-turbo-er/wa/ingest/gdelt.py

import asyncio
import httpx
import pandas as pd
from datetime import datetime, timedelta, timezone
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed
import zipfile
import io
import duckdb

# from ..config import config # This import was unused and incorrect
from ..db import get_db_connection, GDELT_MENTIONS_TABLE # Import the constant

# GDELT 2.0 Master File List URL
GDELT_MASTER_URL = "http://data.gdeltproject.org/gdeltv2/masterfilelist.txt"
GDELT_MENTIONS_COLS = [ # From GDELT 2.0 Mentions Table Codebook
    "GlobalEventID", "EventTimeDate", "MentionTimeDate", "MentionType", "MentionSourceName",
    "MentionIdentifier", "SentenceID", "Actor1CharOffset", "Actor2CharOffset", "ActionCharOffset",
    "InRawText", "Confidence", "MentionDocLen", "MentionDocTone", "MentionDocTranslationInfo",
    "Extras"
]
# GDELT_MENTIONS_TABLE = "gdelt_mentions" # Now imported


async def get_latest_gdelt_file_url(file_type: str = "mentions") -> str | None:
    """
    Fetches the master file list and finds the URL for the latest GDELT file of a specific type.
    Types: 'mentions', 'gkg', 'events'
    """
    logger.info(f"Fetching GDELT master file list to find latest '{file_type}' file...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(GDELT_MASTER_URL, timeout=30.0)
            response.raise_for_status()
            master_list = response.text.strip().split('\n')

            # Filter for the desired file type and find the latest one (last in the list)
            # Format: size hash url (e.g., 12345 abcdef... http://data.gdeltproject.org/gdeltv2/20231026010000.mentions.CSV.zip)
            file_urls = [line.split()[-1] for line in master_list if f".{file_type}.CSV.zip" in line]

            if not file_urls:
                logger.warning(f"No '{file_type}' files found in GDELT master list.")
                return None

            latest_url = file_urls[-1]
            logger.success(f"Found latest GDELT '{file_type}' file URL: {latest_url}")
            return latest_url

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching GDELT master list: {e.response.status_code} - {e.request.url}")
            return None
        except Exception as e:
            logger.error(f"Error fetching or parsing GDELT master list: {e}")
            return None

@retry(stop=stop_after_attempt(3), wait=wait_fixed(10))
async def download_and_process_gdelt_mentions(url: str, keyword_filter: list[str] | None = None, theme_filter: list[str] | None = None) -> pd.DataFrame:
    """
    Downloads a GDELT mentions zip file, extracts the CSV, and filters it.
    Note: Filtering requires understanding GDELT GKG themes if using theme_filter.
          Keyword filter searches the MentionIdentifier (URL/article source).
    """
    logger.info(f"Downloading and processing GDELT mentions file: {url}")
    mentions_data = []

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=120.0) # Longer timeout for potentially large files
            response.raise_for_status()
            zip_content = response.content
            logger.info(f"Downloaded {len(zip_content)} bytes from {url}")

            with zipfile.ZipFile(io.BytesIO(zip_content)) as zf:
                csv_filename = zf.namelist()[0] # Assume only one CSV per zip
                logger.info(f"Extracting and reading CSV: {csv_filename}")
                with zf.open(csv_filename) as csvfile:
                    # Read CSV with pandas, specifying separator, no header, and column names
                    df = pd.read_csv(
                        csvfile,
                        sep='\t',
                        header=None,
                        names=GDELT_MENTIONS_COLS,
                        encoding='latin-1', # GDELT often uses latin-1
                        on_bad_lines='skip' # Skip rows with parsing errors
                    )
                    logger.success(f"Read {len(df)} mentions from {csv_filename}")

                    # --- Filtering Logic ---
                    # Example: Keep only mentions of type 'WEB' (news articles etc.)
                    df_filtered = df[df['MentionType'] == 1].copy()
                    logger.info(f"Filtered down to {len(df_filtered)} mentions of Type 1 (WEB).")

                    # Example: Filter by keywords in the source URL/identifier (case-insensitive)
                    if keyword_filter:
                        keywords_pattern = '|'.join(keyword_filter)
                        df_filtered = df_filtered[df_filtered['MentionIdentifier'].str.contains(keywords_pattern, case=False, na=False)]
                        logger.info(f"Filtered by keywords to {len(df_filtered)} mentions.")

                    # Example: Filter by GKG themes (requires parsing 'Extras' column which is complex)
                    # if theme_filter:
                    #    # TODO: Implement parsing of 'Extras' XML/JSON-like field to extract V2Themes
                    #    # This is non-trivial and format varies.
                    #    logger.warning("Theme filtering not yet fully implemented.")
                    #    pass

                    return df_filtered

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error downloading GDELT file {url}: {e.response.status_code}")
            raise # Reraise for tenacity
        except zipfile.BadZipFile:
            logger.error(f"Failed to unzip file from {url}. It might be corrupted or incomplete.")
            return pd.DataFrame() # Return empty DataFrame
        except pd.errors.ParserError as e:
             logger.error(f"Error parsing CSV data from {url}: {e}")
             return pd.DataFrame() # Return empty DataFrame on parsing error
        except Exception as e:
            logger.error(f"Unexpected error processing GDELT file {url}: {e}")
            raise # Reraise unexpected errors for tenacity


async def store_gdelt_mentions(df: pd.DataFrame, con: duckdb.DuckDBPyConnection | None = None):
    """Stores filtered GDELT mentions data into the database."""
    if df.empty:
        logger.info("No GDELT mentions data to store.")
        return

    conn = con or get_db_connection()
    fetched_at = datetime.now(timezone.utc) # Use timezone-aware datetime

    try:
        # Prepare DataFrame for insertion
        df_to_insert = df[[
            "GlobalEventID", "MentionTimeDate", "MentionSourceName", "MentionIdentifier",
            "SentenceID", "MentionDocTone", "Confidence"
        ]].copy()

        # Convert GDELT dates (YYYYMMDDHHMMSS) to Timestamps
        df_to_insert['MentionTimeDate'] = pd.to_datetime(df_to_insert['MentionTimeDate'], format='%Y%m%d%H%M%S', errors='coerce')
        df_to_insert = df_to_insert.dropna(subset=['MentionTimeDate']) # Drop rows where conversion failed

        df_to_insert['MentionTimeDate'] = df_to_insert['MentionTimeDate'].dt.tz_localize(timezone.utc) # Assume UTC

        # Add fetched_at timestamp
        df_to_insert['fetched_at'] = fetched_at

        # Rename columns to match DB schema (adjust schema as needed)
        df_to_insert = df_to_insert.rename(columns={
            "GlobalEventID": "global_event_id",
            "MentionTimeDate": "mention_ts",
            "MentionSourceName": "source_name",
            "MentionIdentifier": "source_url",
            "SentenceID": "sentence_id",
            "MentionDocTone": "doc_tone",
            "Confidence": "confidence"
        })

        # Select final columns in desired order for the table
        final_cols = [
             "global_event_id", "mention_ts", "source_name", "source_url",
             "sentence_id", "doc_tone", "confidence", "fetched_at"
        ]
        df_to_insert = df_to_insert[final_cols]

        logger.info(f"Attempting to insert {len(df_to_insert)} GDELT mentions records.")

        # Use INSERT OR IGNORE to avoid issues with duplicate mentions if run multiple times on same file
        # Requires a PRIMARY KEY or UNIQUE constraint in the table (e.g., on global_event_id + sentence_id?)
        # For simplicity, let's assume duplicates are acceptable or handled by downstream processing for now.
        # If a PK is added, use INSERT OR IGNORE or INSERT ... ON CONFLICT DO NOTHING
        conn.execute(f"CREATE TEMP TABLE temp_gdelt_mentions AS SELECT * FROM df_to_insert")
        conn.execute(f"""
            INSERT INTO {GDELT_MENTIONS_TABLE}
            SELECT * FROM temp_gdelt_mentions
        """)
        # Consider ON CONFLICT clause if PK is defined:
        # INSERT INTO {GDELT_MENTIONS_TABLE} (...) SELECT ... FROM temp_gdelt_mentions
        # ON CONFLICT (primary_key_column(s)) DO NOTHING;
        conn.execute("DROP TABLE temp_gdelt_mentions")

        logger.success(f"Successfully stored {len(df_to_insert)} GDELT mentions records.")

    except Exception as e:
        logger.error(f"Error storing GDELT mentions data: {e}")
        # Decide whether to raise or just log
    finally:
        if not con:
            conn.close()


async def ingest_latest_gdelt_mentions(keyword_filter: list[str] | None = None, con: duckdb.DuckDBPyConnection | None = None):
    """Ingests the latest available GDELT mentions file, filters, and stores it."""
    logger.info("Starting ingestion of latest GDELT mentions...")
    latest_url = await get_latest_gdelt_file_url(file_type="mentions")

    if not latest_url:
        logger.error("Could not find the latest GDELT mentions file URL. Aborting.")
        return

    mentions_df = await download_and_process_gdelt_mentions(latest_url, keyword_filter=keyword_filter)

    if not mentions_df.empty:
        conn_local = con or get_db_connection()
        try:
            await store_gdelt_mentions(mentions_df, con=conn_local)
        finally:
            if not con:
                conn_local.close()
    else:
        logger.warning(f"No mentions data processed from {latest_url} (or filtering removed all data).")

    logger.info("Finished ingestion of latest GDELT mentions.")


# Example Usage
async def main():
    # Example: Filter for mentions from common financial news sources
    financial_keywords = ["bloomberg", "reuters", "wsj.com", "ft.com", "cnbc", "marketwatch"]
    conn = get_db_connection()
    try:
        # Ensure schema exists (including GDELT_MENTIONS_TABLE)
        from .. import db # Import here for example clarity
        db.create_schema(conn)
        await ingest_latest_gdelt_mentions(keyword_filter=financial_keywords, con=conn)
    except Exception as e:
        logger.exception(f"GDELT ingestion example failed: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    asyncio.run(main())
