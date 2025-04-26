# wealtharc-turbo-er/wa/aggregator.py

import asyncio
import duckdb
from loguru import logger
from typing import List, Tuple, Any, Coroutine

from .config import DB_PATH # Import correct specific variable
from .db import get_db_connection, create_schema

# Import ingestor functions
from .ingest.google_trends import ingest_google_trends
from .ingest.wikimedia import ingest_wikipedia_for_query # Correct function name
from .ingest.gdelt import ingest_latest_gdelt_mentions # Correct function name
from .ingest.twitter import ingest_twitter_search # Correct function name
from .ingest.reddit import ingest_reddit_search # Correct function name
from .ingest.stocktwits import ingest_stocktwits_symbol
from .ingest.sec_edgar import ingest_sec_filings
from .ingest.companies_house import search_ch_companies, ingest_companies_house_company # Import search and ingest
from .ingest.uspto import ingest_uspto_patents
from .ingest.epo import ingest_epo_patents
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

async def _run_companies_house_ingestion(company_name: str, con: duckdb.DuckDBPyConnection):
    """Helper to search for CH company number and then ingest."""
    logger.info(f"Companies House: Searching for company number for '{company_name}'")
    companies = await search_ch_companies(query=company_name, items_per_page=1)
    if companies and companies[0].get('company_number'):
        company_number = companies[0]['company_number']
        logger.info(f"Companies House: Found company number {company_number}. Ingesting data...")
        await ingest_companies_house_company(company_number=company_number, con=con)
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
    con = get_db_connection(db_path)

    if create_db_schema:
        logger.info("Ensuring database schema exists...")
        try:
            create_schema(con)
            logger.success("Database schema check/creation complete.")
        except Exception as e:
            logger.error(f"Failed to create/verify database schema: {e}")
            con.close()
            return # Cannot proceed without schema

    tasks = []

    # Map queries to ingestors (adapt as needed)
    # Using query_name for most, query_symbol where appropriate
    symbol_to_use = query_symbol or query_name # Fallback for symbol-based APIs
    name_to_use = query_name

    # Create tasks using the wrapper
    tasks.append(run_single_ingestor(ingest_google_trends(keywords=[name_to_use], timeframe='today 1-m', con=con), "Google Trends")) # Re-added con=con argument
    tasks.append(run_single_ingestor(ingest_wikipedia_for_query(query=name_to_use, con=con), "Wikimedia")) # Use correct function and arg name
    tasks.append(run_single_ingestor(ingest_latest_gdelt_mentions(keyword_filter=[name_to_use], con=con), "GDELT")) # Use correct function and args
    tasks.append(run_single_ingestor(ingest_twitter_search(query=name_to_use, max_results=limit_per_source, con=con), "Twitter/X")) # Use correct function and args
    tasks.append(run_single_ingestor(ingest_reddit_search(subreddit="all", query=name_to_use, limit=limit_per_source, con=con), "Reddit")) # Use correct function and args
    tasks.append(run_single_ingestor(ingest_stocktwits_symbol(symbol=symbol_to_use, limit=limit_per_source, con=con), "StockTwits"))
    tasks.append(run_single_ingestor(ingest_sec_filings(ticker_or_cik=symbol_to_use, filing_type="10-K", limit=limit_per_source, con=con), "SEC EDGAR (10-K)")) # Specify filing type
    tasks.append(run_single_ingestor(_run_companies_house_ingestion(company_name=name_to_use, con=con), "Companies House")) # Use helper
    tasks.append(run_single_ingestor(ingest_uspto_patents(assignee_name=name_to_use, limit=limit_per_source, con=con), "USPTO"))
    tasks.append(run_single_ingestor(ingest_epo_patents(applicant_name=name_to_use, limit=limit_per_source, con=con), "EPO"))

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

    # Close the connection
    if con:
        con.close()
        logger.debug("Database connection closed.")

# Example of how to run this (e.g., in a test script)
async def main_aggregator_test():
    test_company_name = "Apple Inc."
    test_ticker = "AAPL"
    await run_all_ingestors(query_name=test_company_name, query_symbol=test_ticker)

if __name__ == "__main__":
    # This allows running the aggregator directly for a quick test
    # Configure logging
    # from loguru import logger
    # logger.add("logs/aggregator_run_{time}.log", rotation="5 MB")
    logger.info("Running aggregator test directly...")
    asyncio.run(main_aggregator_test())
