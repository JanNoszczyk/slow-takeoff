# wealtharc-turbo-er/wa/ingest/google_trends.py

import asyncio
from datetime import datetime, timedelta
import pandas as pd
from pytrends.request import TrendReq
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
import duckdb # Import duckdb
import functools # Import functools

# from ..config import config # This import was unused and incorrect
from ..db import get_db_connection, GOOGLE_TRENDS_TABLE

def _sync_fetch_google_trends(keywords: list[str], timeframe: str, geo: str) -> pd.DataFrame:
    """Synchronous helper to fetch Google Trends data."""
    try:
        # Initialize TrendReq inside the sync function (runs in executor thread)
        pytrends = TrendReq(hl='en-US', tz=360)
        pytrends.build_payload(kw_list=keywords, cat=0, timeframe=timeframe, geo=geo, gprop='')
        interest_over_time_df = pytrends.interest_over_time()
        return interest_over_time_df
    except Exception as e:
        # Log error from within the sync function context if needed,
        # but primarily let the async wrapper handle logging.
        logger.debug(f"Sync Google Trends fetch failed internally: {e}")
        raise # Re-raise to be caught by the executor/async wrapper

async def fetch_google_trends(keywords: list[str], timeframe: str = 'today 3-m', geo: str = '') -> pd.DataFrame:
    """
    Fetches Google Trends interest over time for a list of keywords.

    Args:
        keywords: A list of keywords to query. Max 5 per request.
        timeframe: Timeframe for the data (e.g., 'today 5-y', 'today 3-m', 'now 7-d').
        geo: Geographic region (e.g., 'US', 'GB', ''). Empty string for worldwide.

    Returns:
        A pandas DataFrame with interest scores, or an empty DataFrame if an error occurs.
    """
    logger.info(f"Fetching Google Trends for keywords: {keywords}, timeframe: {timeframe}, geo: {geo}")
    if not keywords:
        logger.warning("No keywords provided for Google Trends fetch.")
        return pd.DataFrame()
    if len(keywords) > 5:
        logger.warning("Google Trends API allows a maximum of 5 keywords per request. Truncating list.")
        keywords = keywords[:5]

    loop = asyncio.get_running_loop()
    try:
        # Run the synchronous helper function in the executor
        interest_over_time_df = await loop.run_in_executor(
            None, _sync_fetch_google_trends, keywords, timeframe, geo
        )

        if interest_over_time_df is None or interest_over_time_df.empty:
            logger.warning(f"No Google Trends data returned for keywords: {keywords}")
            return pd.DataFrame()

        # Rename columns and reset index to make it easier to process
        interest_over_time_df = interest_over_time_df.reset_index()
        # Drop the 'isPartial' column if it exists
        if 'isPartial' in interest_over_time_df.columns:
            interest_over_time_df = interest_over_time_df.drop(columns=['isPartial'])

        # Melt the DataFrame to long format
        melted_df = interest_over_time_df.melt(id_vars=['date'], var_name='keyword', value_name='interest_score')

        logger.success(f"Successfully fetched Google Trends data for keywords: {keywords}")
        return melted_df

    except Exception as e:
        logger.error(f"Error fetching Google Trends for {keywords}: {e}")
        # Handle specific pytrends exceptions if necessary, e.g., ResponseError
        return pd.DataFrame()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(5),
    retry=retry_if_exception_type(Exception),
    reraise=True
)
async def store_google_trends_data(df: pd.DataFrame, geo: str = '', db_path: str | None = None):
    """Stores fetched Google Trends data into the database."""
    if df.empty:
        logger.info("No Google Trends data to store.")
        return

    # Prepare data outside the thread
    df_prepared = df.copy()
    df_prepared['geo'] = geo if geo else 'WW'
    df_prepared['source'] = 'google_trends'
    df_prepared['fetched_at'] = datetime.utcnow()
    # Ensure date is in date format for ID generation
    df_prepared['date'] = pd.to_datetime(df_prepared['date']).dt.date
    # Generate trend_id: keyword_YYYY-MM-DD_geo
    df_prepared['trend_id'] = df_prepared.apply(
        lambda row: f"{row['keyword']}_{row['date'].isoformat()}_{row['geo']}", axis=1
    )
    # Ensure correct column order for INSERT
    df_prepared = df_prepared[['trend_id', 'keyword', 'date', 'interest_score', 'geo', 'source', 'fetched_at']]


    try:
        # Define the database operations to run in the thread
        def db_operations_in_thread(path: str | None, data_frame: pd.DataFrame):
            conn = None
            try:
                conn = get_db_connection(path) # Create connection inside thread
                table_name = GOOGLE_TRENDS_TABLE
                # Create a temporary table from the DataFrame *within the connection*
                conn.execute("CREATE TEMP TABLE temp_trends AS SELECT * FROM data_frame")
                # Perform the INSERT OR REPLACE using the temporary table, now including trend_id
                conn.execute(f"""
                    INSERT OR REPLACE INTO {table_name} (trend_id, keyword, date, interest_score, geo, source, fetched_at)
                    SELECT trend_id, keyword, date, interest_score, geo, source, fetched_at
                    FROM temp_trends
                """)
                conn.execute("DROP TABLE temp_trends") # Drop the temporary table
                logger.success(f"Thread successfully stored {len(data_frame)} Google Trends records.")
            except Exception as thread_e:
                logger.error(f"Error in thread storing Google Trends data: {thread_e}")
                raise # Re-raise to be caught by the main async task
            finally:
                if conn:
                    conn.close() # Close connection inside thread
                    logger.debug("Thread closed Google Trends DB connection.")

        # Run the entire operation (connect, execute, close) in a separate thread
        await asyncio.to_thread(db_operations_in_thread, db_path, df_prepared)

    except Exception as e:
        logger.error(f"Error storing Google Trends data: {e}")
        raise # Re-raise after logging


async def ingest_google_trends(keywords: list[str], timeframe: str = 'today 3-m', geo: str = '', db_path: str | None = None):
    """Fetches and stores Google Trends data for the given keywords."""
    logger.info(f"Starting Google Trends ingestion for keywords: {keywords}")
    try:
        trends_df = await fetch_google_trends(keywords, timeframe, geo)
        if not trends_df.empty:
            # Pass db_path down to the storage function instead of con
            await store_google_trends_data(trends_df, geo, db_path=db_path)
    except Exception as e:
        logger.error(f"Google Trends ingestion failed for {keywords}: {e}", exc_info=True)
        # Decide if the main ingestor should raise or just log
        # raise # Option: propagate error up to aggregator
    finally:
        logger.info(f"Finished Google Trends ingestion for keywords: {keywords}")


# Example Usage (can be called from Streamlit app or elsewhere)
async def main():
    # Example: Fetch trends for asset-related keywords
    asset_keywords = ["bitcoin", "tesla stock", "gold price", "nvidia", "inflation"] # Max 5
    test_db_path = "test_gtrends.db" # Use a test-specific db path
    conn = None
    try:
        # Ensure schema exists
        conn = get_db_connection(test_db_path)
        from .. import db # Import here for example clarity
        db.create_schema(conn)
        conn.close() # Close schema check connection
        conn = None # Reset conn variable

        await ingest_google_trends(asset_keywords, db_path=test_db_path) # Pass db_path
    except Exception as e:
        logger.exception(f"Google Trends example failed: {e}")
    finally:
        if conn: # Ensure connection is closed if schema creation failed
            conn.close()
        # Clean up test db file
        import os
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
            logger.info(f"Cleaned up test database: {test_db_path}")


if __name__ == "__main__":
    # Configure Loguru for better logging
    # import sys
    # loguru_config = {
    #     "handlers": [
    #         {"sink": sys.stderr, "level": "INFO"},
    #         {"sink": "logs/ingest_google_trends.log", "level": "DEBUG", "rotation": "10 MB"},
    #     ],
    # }
    # logger.configure(**loguru_config) # Requires loguru setup elsewhere

    # For standalone testing:
    asyncio.run(main())
