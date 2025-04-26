# wealtharc-turbo-er/wa/ingest/wikimedia.py

import asyncio
import wikipedia
from datetime import datetime, timezone
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
import duckdb
import json # Import json for payload parsing

# Import constants and connection function
from ..db import get_db_connection, WIKIMEDIA_CONTENT_TABLE, RAW_WIKIMEDIA_TABLE

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2), retry=retry_if_exception_type(wikipedia.exceptions.WikipediaException))
async def search_wikipedia(query: str, results: int = 1) -> list[str]:
    """Searches Wikipedia and returns page titles."""
    logger.info(f"Searching Wikipedia for query: '{query}', results: {results}")
    loop = asyncio.get_running_loop()
    try:
        titles = await loop.run_in_executor(None, lambda: wikipedia.search(query, results=results))
        logger.success(f"Found {len(titles)} Wikipedia page(s) for '{query}': {titles}")
        return titles
    except wikipedia.exceptions.WikipediaException as e:
        logger.error(f"Wikipedia search failed for '{query}': {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during Wikipedia search for '{query}': {e}")
        return []

@retry(stop=stop_after_attempt(3), wait=wait_fixed(3), retry=retry_if_exception_type(wikipedia.exceptions.WikipediaException))
async def fetch_wikipedia_summary(title: str, sentences: int = 5) -> str | None:
    """Fetches the summary of a Wikipedia page."""
    logger.info(f"Fetching Wikipedia summary for page: '{title}'")
    loop = asyncio.get_running_loop()
    try:
        page = await loop.run_in_executor(None, lambda: wikipedia.page(title, auto_suggest=False, redirect=True))
        summary = await loop.run_in_executor(None, lambda: page.summary)
        logger.success(f"Successfully fetched summary for '{title}' (Length: {len(summary)})")
        return summary
    except wikipedia.exceptions.PageError:
        logger.warning(f"Wikipedia page not found for title: '{title}'")
        return None
    except wikipedia.exceptions.DisambiguationError as e:
        logger.warning(f"Wikipedia disambiguation error for '{title}': {e.options[:5]}...")
        return None
    except wikipedia.exceptions.WikipediaException as e:
        logger.error(f"Wikipedia fetch failed for '{title}': {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching Wikipedia summary for '{title}': {e}")
        return None


async def store_raw_wikimedia_data(page_title: str, summary: str, db_path: str | None = None):
    """Stores the fetched Wikipedia summary into the raw table."""
    if not summary:
        logger.debug(f"No summary provided for '{page_title}', skipping raw storage.")
        return

    fetched_at = datetime.utcnow()
    page_id = page_title.replace(" ", "_").lower()
    payload_str = json.dumps({
        "title": page_title,
        "summary": summary,
        "url": f"https://en.wikipedia.org/wiki/{page_title.replace(' ', '_')}"
    })
    record_data = [page_id, fetched_at, payload_str]

    try:
        def db_operations_in_thread(path: str | None, data: list):
            conn = None
            try:
                conn = get_db_connection(path) # Create connection inside thread
                sql = f"""
                    INSERT INTO {RAW_WIKIMEDIA_TABLE} (id, fetched_at, payload)
                    VALUES (?, ?, ?)
                    ON CONFLICT (id) DO UPDATE SET
                        fetched_at = excluded.fetched_at,
                        payload = excluded.payload;
                    """
                conn.execute(sql, data) # Use connection
                logger.success(f"Thread stored/updated raw Wikipedia data for ID: {data[0]}")
            except Exception as thread_e:
                logger.error(f"Error in thread storing raw Wikipedia data for {data[0]}: {thread_e}")
                raise # Re-raise to be caught by main async task
            finally:
                if conn: conn.close(); logger.debug(f"Thread closed raw Wikimedia DB connection for {data[0]}.") # Close connection inside thread

        await asyncio.to_thread(db_operations_in_thread, db_path, record_data)

    except Exception as e:
        logger.error(f"Error storing raw Wikipedia data for {page_id}: {e}")
        raise # Re-raise error caught from thread


async def store_wikimedia_content(page_id: str, page_title: str, summary: str, url: str, db_path: str | None = None):
    """Stores cleaned Wikimedia content into the dedicated table."""
    if not summary:
        logger.debug(f"No summary provided for '{page_title}', skipping cleaned storage.")
        return

    last_fetched_at = datetime.utcnow()
    record_data = [page_id, page_title, summary, url, last_fetched_at]

    try:
        def db_operations_in_thread(path: str | None, data: list):
            conn = None
            try:
                conn = get_db_connection(path) # Create connection inside thread
                # Corrected SQL: Use 'extract' instead of 'summary', remove 'last_fetched_at'
                # Also assuming 'fetched_at' should be set based on db.py schema
                sql = f"""
                    INSERT INTO {WIKIMEDIA_CONTENT_TABLE} (page_id, title, extract, url, fetched_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT (page_id) DO UPDATE SET
                        title = excluded.title, extract = excluded.extract,
                        url = excluded.url, fetched_at = excluded.fetched_at;
                    """
                # The 'data' list needs to match the VALUES (?, ?, ?, ?, ?)
                # It currently is [page_id, page_title, summary, url, last_fetched_at]
                # Adjusting the data list passed to execute:
                adjusted_data = data[:4] + [data[4]] # Use page_id, title, summary(for extract), url, fetched_at
                conn.execute(sql, adjusted_data) # Use connection with adjusted data
                logger.success(f"Thread stored/updated cleaned Wikimedia content for page_id: {data[0]}")
            except Exception as thread_e:
                logger.error(f"Error in thread storing cleaned Wikimedia content for {data[0]}: {thread_e}")
                raise
            finally:
                if conn: conn.close(); logger.debug(f"Thread closed cleaned Wikimedia DB connection for {data[0]}.") # Close connection inside thread

        await asyncio.to_thread(db_operations_in_thread, db_path, record_data)

    except Exception as e:
        logger.error(f"Error storing cleaned Wikimedia content for {page_id}: {e}")
        raise # Re-raise error caught from thread


async def ingest_wikipedia_for_query(query: str, store_raw: bool = True, db_path: str | None = None):
    """Searches Wikipedia for a query, fetches the top summary, and stores it."""
    logger.info(f"Starting Wikipedia ingestion for query: '{query}'")
    try:
        titles = await search_wikipedia(query, results=1)
        if not titles:
            logger.warning(f"No Wikipedia pages found for query '{query}'.")
            return

        top_title = titles[0]
        summary = await fetch_wikipedia_summary(top_title)

        if summary:
            page_id = top_title.replace(" ", "_").lower()
            url = f"https://en.wikipedia.org/wiki/{top_title.replace(' ', '_')}"
            try:
                # Run storage tasks sequentially but they use threads internally
                if store_raw:
                     await store_raw_wikimedia_data(top_title, summary, db_path=db_path)
                await store_wikimedia_content(page_id, top_title, summary, url, db_path=db_path)
                logger.success(f"Finished Wikipedia ingestion for query: '{query}' (found '{top_title}')")
            except Exception as store_e:
                # Catch errors raised from storage functions
                logger.error(f"Failed to store Wikipedia data for query '{query}': {store_e}", exc_info=True)
        else:
            logger.warning(f"Could not fetch summary for top result '{top_title}' of query '{query}'.")
    except Exception as e:
         logger.exception(f"Error during Wikipedia ingestion pipeline for '{query}': {e}")
         raise # Propagate fetch errors etc.


# Example Usage
async def main():
    test_queries = ["Microsoft", "Nvidia", "ECB quantitative easing", "BlackRock Inc."]
    test_db_path = "test_wikimedia.db"
    conn = None
    try:
        conn = get_db_connection(test_db_path)
        from .. import db
        db.create_schema(conn) # Ensure schema exists
        conn.close(); conn = None
        tasks = [ingest_wikipedia_for_query(query, db_path=test_db_path) for query in test_queries]
        await asyncio.gather(*tasks)
    except Exception as e: logger.exception(f"Wikimedia example failed: {e}")
    finally:
        if conn: conn.close()
        import os
        if os.path.exists(test_db_path): os.remove(test_db_path); logger.info(f"Cleaned up {test_db_path}")

if __name__ == "__main__":
    asyncio.run(main())
