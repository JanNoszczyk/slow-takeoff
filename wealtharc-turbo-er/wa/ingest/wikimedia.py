# wealtharc-turbo-er/wa/ingest/wikimedia.py

import asyncio
import wikipedia
from datetime import datetime
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
import duckdb
import json # Import json for payload parsing

# from ..config import config # This import was unused and incorrect
from ..db import get_db_connection, WIKIMEDIA_CONTENT_TABLE # Import the constant

# Use constants from db.py where possible
RAW_WIKIMEDIA_TABLE = "raw_wikimedia"
# WIKIMEDIA_CONTENT_TABLE = "wikimedia_content" # Now imported

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2), retry=retry_if_exception_type(wikipedia.exceptions.WikipediaException))
async def search_wikipedia(query: str, results: int = 1) -> list[str]:
    """Searches Wikipedia and returns page titles."""
    logger.info(f"Searching Wikipedia for query: '{query}', results: {results}")
    loop = asyncio.get_running_loop()
    try:
        # wikipedia library is synchronous, run in executor
        # Pass keyword arguments correctly to the function being executed
        titles = await loop.run_in_executor(None, lambda: wikipedia.search(query, results=results))
        logger.success(f"Found {len(titles)} Wikipedia page(s) for '{query}': {titles}")
        return titles
    except wikipedia.exceptions.WikipediaException as e:
        logger.error(f"Wikipedia search failed for '{query}': {e}")
        raise # Reraise for tenacity
    except Exception as e:
        logger.error(f"Unexpected error during Wikipedia search for '{query}': {e}")
        return [] # Don't retry unexpected errors

@retry(stop=stop_after_attempt(3), wait=wait_fixed(3), retry=retry_if_exception_type(wikipedia.exceptions.WikipediaException))
async def fetch_wikipedia_summary(title: str, sentences: int = 5) -> str | None:
    """Fetches the summary of a Wikipedia page."""
    logger.info(f"Fetching Wikipedia summary for page: '{title}'")
    loop = asyncio.get_running_loop()
    try:
        # Set language if needed: wikipedia.set_lang("en")
        # Correctly pass keyword arguments within the executor call
        page = await loop.run_in_executor(None, lambda: wikipedia.page(title, auto_suggest=False, redirect=True))
        # Fetch summary using page object method
        summary = await loop.run_in_executor(None, lambda: page.summary)
        # summary = await loop.run_in_executor(None, lambda: wikipedia.summary(title, sentences=sentences, auto_suggest=False)) # Alternative direct summary
        logger.success(f"Successfully fetched summary for '{title}' (Length: {len(summary)})")
        return summary
    except wikipedia.exceptions.PageError:
        logger.warning(f"Wikipedia page not found for title: '{title}'")
        return None
    except wikipedia.exceptions.DisambiguationError as e:
        logger.warning(f"Wikipedia disambiguation error for '{title}': {e.options[:5]}...") # Show some options
        # Could try fetching the first option?
        # try:
        #     first_option = e.options[0]
        #     logger.info(f"Attempting fetch for first disambiguation option: '{first_option}'")
        #     return await fetch_wikipedia_summary(first_option, sentences)
        # except Exception as inner_e:
        #     logger.error(f"Failed fetching disambiguation option '{e.options[0]}': {inner_e}")
        return None # Return None for disambiguation for now
    except wikipedia.exceptions.WikipediaException as e:
        logger.error(f"Wikipedia fetch failed for '{title}': {e}")
        raise # Reraise for tenacity
    except Exception as e:
        logger.error(f"Unexpected error fetching Wikipedia summary for '{title}': {e}")
        return None # Don't retry unexpected errors


async def store_raw_wikimedia_data(page_title: str, summary: str, con: duckdb.DuckDBPyConnection | None = None):
    """Stores the fetched Wikipedia summary into the raw table."""
    if not summary:
        logger.debug(f"No summary provided for '{page_title}', skipping raw storage.")
        return

    conn = con or get_db_connection()
    fetched_at = datetime.utcnow()
    # Use page title as a unique ID for this raw entry (could use page ID if fetched)
    page_id = page_title.replace(" ", "_").lower() # Simple ID generation

    # Create JSON payload
    payload = {
        "title": page_title,
        "summary": summary,
        "url": f"https://en.wikipedia.org/wiki/{page_title.replace(' ', '_')}" # Construct URL
    }

    try:
        conn.execute(
            f"""
            INSERT INTO {RAW_WIKIMEDIA_TABLE} (id, fetched_at, payload)
            VALUES (?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                fetched_at = excluded.fetched_at,
                payload = excluded.payload;
            """,
            [page_id, fetched_at, payload]
        )
        logger.info(f"Stored/Updated raw Wikipedia data for ID: {page_id}")
    except Exception as e:
        logger.error(f"Error storing raw Wikipedia data for {page_id}: {e}")
    finally:
        # Close connection only if it was opened locally in this function
        if not con:
            conn.close()


async def store_wikimedia_content(page_id: str, page_title: str, summary: str, url: str, con: duckdb.DuckDBPyConnection):
    """Stores cleaned Wikimedia content into the dedicated table."""
    if not summary:
        logger.debug(f"No summary provided for '{page_title}', skipping cleaned storage.")
        return

    last_fetched_at = datetime.utcnow()

    try:
        conn = con # Assume connection is passed
        conn.execute(
            f"""
            INSERT INTO {WIKIMEDIA_CONTENT_TABLE} (page_id, title, summary, url, last_fetched_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (page_id) DO UPDATE SET
                title = excluded.title,
                summary = excluded.summary,
                url = excluded.url,
                last_fetched_at = excluded.last_fetched_at;
            """,
            [page_id, page_title, summary, url, last_fetched_at]
        )
        logger.info(f"Stored/Updated cleaned Wikimedia content for page_id: {page_id}")

    except Exception as e:
        logger.error(f"Error storing cleaned Wikimedia content for {page_id}: {e}")
        # Decide if this should raise or just log


async def ingest_wikipedia_for_query(query: str, store_raw: bool = True, con: duckdb.DuckDBPyConnection | None = None):
    """Searches Wikipedia for a query, fetches the top summary, and stores it."""
    logger.info(f"Starting Wikipedia ingestion for query: '{query}'")
    titles = await search_wikipedia(query, results=1)

    if not titles:
        logger.warning(f"No Wikipedia pages found for query '{query}'.")
        return

    top_title = titles[0]
    summary = await fetch_wikipedia_summary(top_title)

    if summary:
        conn_local = con or get_db_connection() # Use provided or get new connection
        try:
            page_id = top_title.replace(" ", "_").lower() # Reuse the simple ID
            url = f"https://en.wikipedia.org/wiki/{top_title.replace(' ', '_')}" # Reuse URL

            if store_raw:
                await store_raw_wikimedia_data(top_title, summary, con=conn_local)

            # Store cleaned data
            await store_wikimedia_content(page_id, top_title, summary, url, con=conn_local)

        finally:
             # Close connection only if it was opened locally in this function
            if not con:
                conn_local.close()
        logger.success(f"Finished Wikipedia ingestion for query: '{query}' (found '{top_title}')")
    else:
        logger.warning(f"Could not fetch summary for top result '{top_title}' of query '{query}'.")


# Example Usage
async def main():
    test_queries = ["Microsoft", "Nvidia", "ECB quantitative easing", "BlackRock Inc."]
    conn = get_db_connection()
    # Import db module inside main for example usage clarity if needed
    from .. import db
    conn = get_db_connection()
    try:
        # Ensure schema exists (including raw_wikimedia and wikimedia_content)
        db.create_schema(conn)
        tasks = [ingest_wikipedia_for_query(query, con=conn) for query in test_queries]
        await asyncio.gather(*tasks)
    finally:
        conn.close()

if __name__ == "__main__":
    asyncio.run(main())
