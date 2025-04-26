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
    """
    logger.info(f"Downloading and processing GDELT mentions file: {url}")
    mentions_data = []

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=120.0) # Longer timeout
            response.raise_for_status()
            zip_content = response.content
            logger.info(f"Downloaded {len(zip_content)} bytes from {url}")

            with zipfile.ZipFile(io.BytesIO(zip_content)) as zf:
                csv_filename = zf.namelist()[0]
                logger.info(f"Extracting and reading CSV: {csv_filename}")
                with zf.open(csv_filename) as csvfile:
                    df = pd.read_csv(
                        csvfile, sep='\t', header=None, names=GDELT_MENTIONS_COLS,
                        encoding='latin-1', on_bad_lines='skip'
                    )
                    logger.success(f"Read {len(df)} mentions from {csv_filename}")

                    df_filtered = df[df['MentionType'] == 1].copy()
                    logger.info(f"Filtered down to {len(df_filtered)} mentions of Type 1 (WEB).")

                    if keyword_filter:
                        keywords_pattern = '|'.join(keyword_filter)
                        df_filtered = df_filtered[df_filtered['MentionIdentifier'].str.contains(keywords_pattern, case=False, na=False)]
                        logger.info(f"Filtered by keywords to {len(df_filtered)} mentions.")

                    # Placeholder for theme filtering
                    # if theme_filter: ...

                    return df_filtered

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error downloading GDELT file {url}: {e.response.status_code}")
            raise
        except zipfile.BadZipFile:
            logger.error(f"Failed to unzip file from {url}.")
            return pd.DataFrame()
        except pd.errors.ParserError as e:
             logger.error(f"Error parsing CSV data from {url}: {e}")
             return pd.DataFrame()
        except Exception as e:
            logger.error(f"Unexpected error processing GDELT file {url}: {e}")
            raise


async def store_gdelt_mentions(df: pd.DataFrame, db_path: str | None = None):
    """Stores filtered GDELT mentions data into the database."""
    if df.empty:
        logger.info("No GDELT mentions data to store.")
        return

    # Prepare DataFrame outside the thread
    df_to_insert = df[[
        "GlobalEventID", "MentionTimeDate", "MentionSourceName", "MentionIdentifier",
        "SentenceID", "MentionDocTone", "Confidence"
    ]].copy()
    df_to_insert['MentionTimeDate'] = pd.to_datetime(df_to_insert['MentionTimeDate'], format='%Y%m%d%H%M%S', errors='coerce')
    df_to_insert = df_to_insert.dropna(subset=['MentionTimeDate'])
    df_to_insert['MentionTimeDate'] = df_to_insert['MentionTimeDate'].dt.tz_localize(timezone.utc)
    df_to_insert['fetched_at'] = datetime.now(timezone.utc)
    df_to_insert = df_to_insert.rename(columns={
        "GlobalEventID": "global_event_id", "MentionTimeDate": "mention_ts",
        "MentionSourceName": "source_name", "MentionIdentifier": "source_url",
        "SentenceID": "sentence_id", "MentionDocTone": "doc_tone", "Confidence": "confidence"
    })
    final_cols = ["global_event_id", "mention_ts", "source_name", "source_url",
                  "sentence_id", "doc_tone", "confidence", "fetched_at"]
    df_to_insert = df_to_insert[final_cols]

    logger.info(f"Attempting to store {len(df_to_insert)} GDELT mentions records.")

    try:
        # Define DB operation to run in thread
        def db_operations_in_thread(path: str | None, data_frame: pd.DataFrame):
            conn = None
            try:
                conn = get_db_connection(path)
                # Use data_frame passed as argument
                conn.execute("CREATE TEMP TABLE temp_gdelt_mentions AS SELECT * FROM data_frame")
                conn.execute(f"""
                    INSERT INTO {GDELT_MENTIONS_TABLE}
                    SELECT * FROM temp_gdelt_mentions
                """)
                conn.execute("DROP TABLE temp_gdelt_mentions")
                logger.success(f"Thread successfully stored {len(data_frame)} GDELT mentions records.")
            except Exception as thread_e:
                logger.error(f"Error in thread storing GDELT mentions data: {thread_e}")
                raise
            finally:
                if conn:
                    conn.close()
                    logger.debug("Thread closed GDELT DB connection.")

        # Run the operation in thread
        await asyncio.to_thread(db_operations_in_thread, db_path, df_to_insert)

    except Exception as e:
        logger.error(f"Error storing GDELT mentions data: {e}")
        raise


async def ingest_latest_gdelt_mentions(keyword_filter: list[str] | None = None, db_path: str | None = None):
    """Ingests the latest available GDELT mentions file, filters, and stores it."""
    logger.info("Starting ingestion of latest GDELT mentions...")
    try:
        latest_url = await get_latest_gdelt_file_url(file_type="mentions")
        if not latest_url:
            logger.error("Could not find the latest GDELT mentions file URL. Aborting.")
            return

        mentions_df = await download_and_process_gdelt_mentions(latest_url, keyword_filter=keyword_filter)

        if not mentions_df.empty:
            try:
                await store_gdelt_mentions(mentions_df, db_path=db_path) # Pass db_path
            except Exception as store_e:
                 logger.error(f"Failed to store GDELT mentions: {store_e}", exc_info=True)
        else:
            logger.warning(f"No mentions data processed from {latest_url} (or filtering removed all data).")

    except Exception as e:
         logger.exception(f"Error during GDELT ingestion pipeline: {e}")
         raise # Propagate unexpected errors
    finally:
        logger.info("Finished ingestion of latest GDELT mentions.")


# Example Usage
async def main():
    financial_keywords = ["bloomberg", "reuters", "wsj.com", "ft.com", "cnbc", "marketwatch"]
    test_db_path = "test_gdelt.db"
    conn = None
    try:
        conn = get_db_connection(test_db_path)
        from .. import db
        db.create_schema(conn)
        conn.close()
        conn = None
        await ingest_latest_gdelt_mentions(keyword_filter=financial_keywords, db_path=test_db_path)
    except Exception as e:
        logger.exception(f"GDELT ingestion example failed: {e}")
    finally:
        if conn: # If schema creation failed
            conn.close()
        import os
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
            logger.info(f"Cleaned up test database: {test_db_path}")

if __name__ == "__main__":
    asyncio.run(main())
