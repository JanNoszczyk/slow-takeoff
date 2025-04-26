# wealtharc-turbo-er/wa/ingest/google_trends.py

import asyncio
from datetime import datetime, timedelta
import pandas as pd
from pytrends.request import TrendReq
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
import duckdb # Import duckdb

# from ..config import config # This import was unused and incorrect
from ..db import get_db_connection, GOOGLE_TRENDS_TABLE

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
        # pytrends is not inherently async, so run it in a thread pool executor
        pytrends = await loop.run_in_executor(None, TrendReq, {'hl': 'en-US', 'tz': 360})
        await loop.run_in_executor(None, pytrends.build_payload, keywords, {'cat': 0, 'timeframe': timeframe, 'geo': geo, 'gprop': ''})
        interest_over_time_df = await loop.run_in_executor(None, pytrends.interest_over_time)

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
async def store_google_trends_data(df: pd.DataFrame, geo: str = '', con: duckdb.DuckDBPyConnection | None = None):
    """Stores fetched Google Trends data into the database."""
    if df.empty:
        logger.info("No Google Trends data to store.")
        return

    conn_local = None # Track if we opened a connection locally
    try:
        conn = con or get_db_connection()
        if not con: # If we fetched a new connection
             conn_local = conn
        table_name = GOOGLE_TRENDS_TABLE

        # Add geo and source columns
        df['geo'] = geo if geo else 'WW' # Use 'WW' for worldwide
        df['source'] = 'google_trends'
        df['fetched_at'] = datetime.utcnow()

        # Ensure columns match the expected schema (adjust as needed)
        df = df[['keyword', 'date', 'interest_score', 'geo', 'source', 'fetched_at']]
        df['date'] = pd.to_datetime(df['date']).dt.date # Ensure date format

        # Use DuckDB's efficient DataFrame insertion
        # We'll use INSERT OR REPLACE to handle potential duplicate entries for the same keyword-date-geo combo
        # This requires a unique constraint on (keyword, date, geo) in the table definition.
        conn.execute(f"CREATE TEMP TABLE temp_trends AS SELECT * FROM df")
        conn.execute(f"""
            INSERT OR REPLACE INTO {table_name} (keyword, date, interest_score, geo, source, fetched_at)
            SELECT keyword, date, interest_score, geo, source, fetched_at
            FROM temp_trends
        """)
        conn.execute("DROP TABLE temp_trends")

        logger.success(f"Successfully stored {len(df)} Google Trends records.")

    except Exception as e:
        logger.error(f"Error storing Google Trends data: {e}")
        raise # Reraise after logging to trigger tenacity retry

    finally:
        # Only close the connection if it was opened locally in this function
        if conn_local:
            conn_local.close()


async def ingest_google_trends(keywords: list[str], timeframe: str = 'today 3-m', geo: str = '', con: duckdb.DuckDBPyConnection | None = None):
    """Fetches and stores Google Trends data for the given keywords."""
    logger.info(f"Starting Google Trends ingestion for keywords: {keywords}")
    trends_df = await fetch_google_trends(keywords, timeframe, geo)
    if not trends_df.empty:
        # Pass the connection object down to the storage function
        await store_google_trends_data(trends_df, geo, con=con)
    logger.info(f"Finished Google Trends ingestion for keywords: {keywords}")


# Example Usage (can be called from Streamlit app or elsewhere)
async def main():
    # Example: Fetch trends for asset-related keywords
    asset_keywords = ["bitcoin", "tesla stock", "gold price", "nvidia", "inflation"] # Max 5
    await ingest_google_trends(asset_keywords)

if __name__ == "__main__":
    # Configure Loguru for better logging
    # loguru_config = {
    #     "handlers": [
    #         {"sink": sys.stderr, "level": "INFO"},
    #         {"sink": "logs/ingest_google_trends.log", "level": "DEBUG", "rotation": "10 MB"},
    #     ],
    # }
    # logger.configure(**loguru_config) # Requires loguru setup elsewhere

    # For standalone testing:
    asyncio.run(main())
