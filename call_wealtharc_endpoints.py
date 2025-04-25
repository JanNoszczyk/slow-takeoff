#!/usr/bin/env python3
"""
Calls WealthArc GET collection endpoints directly using the wealtharc_client
and logs the responses to a file.
"""

# import requests # No longer needed, using the client module
import os
import logging
from dotenv import load_dotenv
import json
import time

# Import the client functions
import wealtharc_client

# --- Configuration ---
# GATEWAY_BASE_URL = "http://localhost:8000" # No longer needed
LOG_FILE = "wealtharc_api_responses.log"
REQUESTS_PER_ENDPOINT = 2 # Changed from 5 to 2
# Map entity set names to client functions, including descriptions
ENTITY_FUNCTION_MAP = {
    # /Assets: Returns financial asset details (Instruments, CashAccounts) including identifiers, classification, risk scores.
    "Assets": wealtharc_client.get_assets,
    # /Portfolios: Returns portfolio records with metadata like name, custodian, currency, managers, status, type.
    "Portfolios": wealtharc_client.get_portfolios,
    # /Positions: Returns asset holdings within portfolios for specific dates, including quantity, price, allocation, FX rates.
    "Positions": wealtharc_client.get_positions,
    # /Transactions: Returns financial transaction details like type, dates, quantity, price, currencies, order IDs.
    "Transactions": wealtharc_client.get_transactions,
    # /PortfoliosDailyMetrics: Returns daily summary metrics for portfolios (e.g., overdraft count, potentially AUM/performance).
    "PortfoliosDailyMetrics": wealtharc_client.get_portfolios_daily_metrics,
}
ENTITY_SETS = list(ENTITY_FUNCTION_MAP.keys()) # Get keys for iteration

# --- Setup ---
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, mode='w'), # Overwrite log file each run
        logging.StreamHandler() # Also print logs to console
    ]
)

# The wealtharc_client module now handles checking for env vars.

# --- Main Execution ---
def call_endpoints():
    for entity_set, client_function in ENTITY_FUNCTION_MAP.items():
        logging.info(f"\n--- Calling API for: {entity_set} ---")

        for i in range(REQUESTS_PER_ENDPOINT):
            attempt = i + 1
            logging.info(f"Attempt {attempt}/{REQUESTS_PER_ENDPOINT} for {entity_set} (limiting to 2 results)")

            # Call the appropriate function from wealtharc_client, limiting results to 2 using the 'top' parameter
            # params = {"$top": 2} # Old way
            response_data = client_function(top=2) # Use the new named argument

            if response_data is not None:
                # Log the JSON formatted nicely
                logging.info(f"  Response Body (Attempt {attempt}):\n{json.dumps(response_data, indent=2)}")
            else:
                # Error is logged within the client's _make_request function
                logging.warning(f"  Failed to get data for {entity_set} on attempt {attempt}.")

            # Optional: Add a small delay between requests if needed
            # time.sleep(1)

    logging.info("\n--- Script finished ---")

if __name__ == "__main__":
    call_endpoints()
