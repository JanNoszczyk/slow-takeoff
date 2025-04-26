# test_ingestion.py

import asyncio
import sys
from loguru import logger

# Adjust the path to import from the wealtharc-turbo-er package
sys.path.insert(0, './wealtharc-turbo-er')

from wa.aggregator import run_all_ingestors
from wa.config import DB_PATH # Import correct specific variable
from wa.db import create_schema, get_db_connection # To ensure schema exists

# Configure Logging
logger.remove() # Remove default handler
logger.add(sys.stderr, level="INFO") # Log INFO and above to console
logger.add(f"logs/ingestion_test_{{time:YYYY-MM-DD}}.log", level="DEBUG", rotation="1 day", retention="7 days") # Log DEBUG and above to a daily file

async def main():
    """Main function to run the ingestion test."""
    # Define the test query
    test_company_name = "Apple Inc."
    test_ticker = "AAPL"
    db_file = DB_PATH # Use correct imported variable

    logger.info(f"Starting ingestion test for Name: '{test_company_name}', Ticker: '{test_ticker}'")
    logger.info(f"Using database: {db_file}")

    # Ensure the database schema exists before running ingestors
    # Although run_all_ingestors does this, doing it explicitly here adds robustness
    try:
        conn = get_db_connection(db_file)
        logger.info("Verifying database schema...")
        create_schema(conn)
        conn.close()
        logger.success("Database schema verified/created.")
    except Exception as e:
        logger.error(f"Failed to set up database schema: {e}", exc_info=True)
        return # Stop if DB setup fails

    # Run the aggregator
    try:
        await run_all_ingestors(
            query_name=test_company_name,
            query_symbol=test_ticker,
            db_path=db_file,
            limit_per_source=15, # Fetch a slightly larger limit for testing
            create_db_schema=False # Schema already created/verified above
        )
        logger.info("Ingestion test run completed.")
    except Exception as e:
        logger.error(f"An error occurred during the ingestion run: {e}", exc_info=True)

if __name__ == "__main__":
    logger.info("Initiating ingestion test...")
    # Create logs directory if it doesn't exist (optional, good practice)
    # import os
    # os.makedirs("logs", exist_ok=True)
    asyncio.run(main())
    logger.info("Ingestion test script finished.")
