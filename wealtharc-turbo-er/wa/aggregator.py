# wealtharc-turbo-er/wa/aggregator.py

import asyncio
import duckdb
from loguru import logger
from typing import List, Tuple, Any, Coroutine

from .config import DB_PATH # Import correct specific variable
from .db import create_schema, get_db_connection # Re-import get_db_connection for schema check

# Import ingestor functions
from .ingest.google_trends import ingest_google_trends
from .ingest.wikimedia import ingest_wikipedia_for_query # Correct function name
from .ingest.gdelt import ingest_latest_gdelt_mentions # Correct function name
from .ingest.stocktwits import ingest_stocktwits_symbol
from .ingest.newsapi import ingest_newsapi_headlines # <-- Import NewsAPI ingestor

# Add other ingestors here if needed

async def run_single_ingestor(ingest_coro: Coroutine, name: str) -> Tuple[str, bool, Any]:
    """Runs a single ingestor coroutine and catches exceptions."""
    try:
        logger.info(f"Starting ingestion for: {name}")
        await ingest_coro
        logger.success(f"Successfully completed ingestion for: {name}")
        return (name, True, None)
    except Exception as e:
        logger.error(f"Ingestion failed for {name}: {e}", exc_info=True)
        return (name, False, e)

async def _run_companies_house_ingestion(company_name: str, db_path: str): # Changed con to db_path
    """Helper to search for CH company number and then ingest."""
    logger.info(f"Companies House: Searching for company number for '{company_name}'")
    companies = await search_ch_companies(query=company_name, items_per_page=1)
    if companies and companies[0].get('company_number'):
        company_number = companies[0]['company_number']
        logger.info(f"Companies House: Found company number {company_number}. Ingesting data...")
        # Pass db_path; ingest_companies_house_company will need updating later
        await ingest_companies_house_company(company_number=company_number, db_path=db_path) # Changed con=con to db_path=db_path
    else:
        logger.warning(f"Companies House: Could not find company number for '{company_name}'. Skipping ingestion.")

async def run_all_ingestors(
    query_name: str,
    query_symbol: str | None = None,
    db_path: str = DB_PATH, # Use correct imported variable
    limit_per_source: int = 10,
    create_db_schema: bool = True,
):
    """
    Runs all configured data ingestors concurrently for a given query.

    Args:
        query_name: The primary name query (e.g., company name, keyword).
        query_symbol: An optional symbol/ticker query (e.g., 'AAPL').
        db_path: Path to the DuckDB database file.
        limit_per_source: Approx max items to fetch per source (actual may vary by API).
        create_db_schema: If True, ensures the DB schema is created/updated.
    """
    logger.info(f"Starting parallel ingestion run for query: '{query_name}' (Symbol: {query_symbol})")
    # REMOVED: con = get_db_connection(db_path)

    if create_db_schema:
        logger.info("Ensuring database schema exists...")
        # Use a temporary connection JUST for schema check/creation
        schema_conn = None
        try:
            schema_conn = get_db_connection(db_path) # Get temp connection
            create_schema(schema_conn) # Check/create schema
            logger.success("Database schema check/creation complete.")
        except Exception as e:
            logger.error(f"Failed to create/verify database schema: {e}")
            if schema_conn: # Ensure it's closed even on error
                 schema_conn.close()
            return # Cannot proceed without schema
        finally:
             if schema_conn: # Close the temp connection
                 schema_conn.close()

    tasks = []

    # Map queries to ingestors (adapt as needed)
    # Using query_name for most, query_symbol where appropriate
    symbol_to_use = query_symbol or query_name # Fallback for symbol-based APIs
    name_to_use = query_name

    # Create tasks using the wrapper - Pass db_path instead of con
    # Individual ingestor functions will need to be updated to accept db_path and manage their own connections.
    tasks.append(run_single_ingestor(ingest_google_trends(keywords=[name_to_use], timeframe='today 1-m', db_path=db_path), "Google Trends"))
    tasks.append(run_single_ingestor(ingest_wikipedia_for_query(query=name_to_use, db_path=db_path), "Wikimedia"))
    tasks.append(run_single_ingestor(ingest_latest_gdelt_mentions(keyword_filter=[name_to_use], db_path=db_path), "GDELT"))
    tasks.append(run_single_ingestor(ingest_stocktwits_symbol(symbol=symbol_to_use, limit=limit_per_source, db_path=db_path), "StockTwits"))
    # Add NewsAPI task - it needs the db_path passed correctly now (will require modification in newsapi.py later if not already done)
    # We pass name_to_use as the query, and use the default max_articles (100) and days_back (30)
    tasks.append(run_single_ingestor(ingest_newsapi_headlines(query=name_to_use, max_articles=limit_per_source, db_path=db_path), "NewsAPI"))


    logger.info(f"Running {len(tasks)} ingestion tasks in parallel...")
    results: List[Tuple[str, bool, Any]] = await asyncio.gather(*tasks)
    logger.info("Parallel ingestion run finished.")

    # Log summary
    successful_tasks = [res[0] for res in results if res[1]]
    failed_tasks = [(res[0], res[2]) for res in results if not res[1]]

    logger.info(f"Successful ingestions ({len(successful_tasks)}): {', '.join(successful_tasks)}")
    if failed_tasks:
        logger.warning(f"Failed ingestions ({len(failed_tasks)}):")
        for name, err in failed_tasks:
            logger.warning(f"  - {name}: {err}")

    # REMOVED: Closing shared connection, as connections are now managed by individual ingestors.
    # if con:
    #     con.close()
    #     logger.debug("Database connection closed.")

# Example of how to run this (e.g., in a test script)
async def main_aggregator_test():
    test_company_name = "Apple Inc."
    test_ticker = "AAPL"
    await run_all_ingestors(query_name=test_company_name, query_symbol=test_ticker) # Fixed indentation

if __name__ == "__main__":
    # This allows running the aggregator directly for a quick test
    # Configure logging
    # from loguru import logger
    # logger.add("logs/aggregator_run_{time}.log", rotation="5 MB")
    logger.info("Running aggregator test directly...")
    asyncio.run(main_aggregator_test())
