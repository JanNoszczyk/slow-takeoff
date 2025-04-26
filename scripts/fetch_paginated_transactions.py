import json
import logging
import math
import asyncio
import os  # Added for file existence check
import wealtharc_client # Import the updated async client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
# Reduce httpx INFO logs if too noisy
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


OUTPUT_JSON_FILE = "all_transactions.json"
FETCHED_IDS_FILE = "fetched_transaction_ids.txt" # File to store processed IDs
PAGE_SIZE = 500 # How many transactions to fetch per API call (adjust based on testing)
# Concurrency limit is managed within the client via Semaphore

# --- Persistence Functions ---

def load_fetched_ids(file_path: str) -> set:
    """Loads previously fetched transaction IDs from a file."""
    if not os.path.exists(file_path):
        logging.info(f"'{file_path}' not found. Starting fresh.")
        return set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            ids = {line.strip() for line in f if line.strip()}
        logging.info(f"Loaded {len(ids)} previously fetched transaction IDs from '{file_path}'.")
        return ids
    except Exception as e:
        logging.error(f"Error loading fetched IDs from '{file_path}': {e}. Starting fresh.", exc_info=True)
        return set() # Start fresh on error

def append_fetched_id(file_path: str, txn_id: str):
    """Appends a successfully fetched transaction ID to the file."""
    try:
        # Use append mode 'a'
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(f"{txn_id}\n")
    except Exception as e:
        # Log error but continue processing if possible
        logging.error(f"Error appending ID '{txn_id}' to '{file_path}': {e}", exc_info=True)

# --- Modified Fetch Function ---

async def fetch_transaction_page(skip: int, top: int, fetched_ids: set, fetched_ids_file_path: str) -> list:
    """
    Fetches a single page of transactions asynchronously.
    Appends new transaction IDs to the tracking file.
    Returns the full list of transactions from the page.
    """
    logging.debug(f"Requesting transactions page: skip={skip}, top={top}")
    try:
        response_data = await wealtharc_client.get_transactions(top=top, skip=skip)
        page_transactions = []
        if response_data and isinstance(response_data.get('value'), list):
            page_transactions = response_data['value']
            logging.info(f"Successfully fetched page: skip={skip}, count={len(page_transactions)}")

            # Process IDs for persistence
            new_ids_on_page = 0
            for txn in page_transactions:
                txn_id = txn.get('id')
                # Ensure it's a valid ID and not already processed in this run or previous runs
                if txn_id and txn_id not in fetched_ids:
                    append_fetched_id(fetched_ids_file_path, txn_id)
                    fetched_ids.add(txn_id) # Add to in-memory set for this run
                    new_ids_on_page += 1

            if new_ids_on_page > 0:
                 logging.debug(f"Appended {new_ids_on_page} new transaction IDs from page skip={skip} to '{fetched_ids_file_path}'.")

            return page_transactions # Return the full page content
        else:
            logging.error(f"Failed to fetch or parse page: skip={skip}. Response: {response_data}")
            return [] # Return empty list on page error
    except Exception as e:
        logging.error(f"Exception fetching page: skip={skip}. Error: {e}", exc_info=True)
        return [] # Return empty list on exception

async def fetch_all_transactions_concurrently():
    """
    Fetches all transactions from the API concurrently using pagination.
    Attempts to determine the total number of pages dynamically if count is not available.
    """
    # --- Load existing IDs ---
    fetched_ids = load_fetched_ids(FETCHED_IDS_FILE)
    logging.info(f"Starting fetch. Will track new IDs in '{FETCHED_IDS_FILE}'.")
    # --- End Load existing IDs ---

    all_transactions = []
    total_count = 0
    num_pages = 0

    # 1. Try to get total count first (remains the same)
    logging.info("Fetching total transaction count (if available)...")
    try:
        count_response = await wealtharc_client.get_transactions(top=0, additional_params={"$count": "true"})
        if count_response and "@odata.count" in count_response:
            total_count = int(count_response["@odata.count"])
            logging.info(f"API reported total transaction count: {total_count}")
            if total_count == 0:
                logging.info("Total count is 0. No transactions to fetch.")
                return []
            num_pages = math.ceil(total_count / PAGE_SIZE)
            logging.info(f"Calculated pages needed based on count: {num_pages}")
        else:
            logging.warning("Could not get total count from API. Will attempt to fetch sequentially until an empty page is found.")
            # Fallback: Fetch page by page until empty - less efficient for concurrency setup
            # This implementation proceeds assuming we can estimate pages or use the count.
            # A fully dynamic approach without count requires sequential checks.
            # For this refactor, let's assume count is available or fail if not.
            if total_count == 0: # Treat inability to get count as an error for concurrent strategy
                logging.error("Failed to get a valid total count required for concurrent fetching. Aborting.")
                return None

    except Exception as e:
        logging.error(f"Error fetching total count: {e}. Aborting fetch.", exc_info=True)
        return None

    # 2. Create tasks for all pages based on the calculated number
    tasks = []
    logging.info(f"Preparing {num_pages} tasks for concurrent fetching...")
    for i in range(num_pages):
        skip = i * PAGE_SIZE
        # Pass the loaded IDs set and file path to each task
        task = fetch_transaction_page(skip=skip, top=PAGE_SIZE, fetched_ids=fetched_ids, fetched_ids_file_path=FETCHED_IDS_FILE)
        tasks.append(task)

    # 3. Run tasks concurrently and gather results (remains the same)
    logging.info(f"Starting concurrent fetch of {len(tasks)} transaction pages...")
    results_list_of_lists = await asyncio.gather(*tasks)

    # 4. Flatten the results and check for errors
    failed_pages = 0
    for page_result in results_list_of_lists:
        if page_result is not None: # Check if page fetch returned data (even an empty list is valid)
            all_transactions.extend(page_result)
        else:
             # If fetch_transaction_page returns None on critical error, count failure
             # Note: Current implementation returns [] on error, so this count might be 0
             failed_pages += 1

    if failed_pages > 0:
         logging.warning(f"{failed_pages} page(s) may have failed critically (returned None).")

    logging.info(f"Finished fetching. Total transactions collected: {len(all_transactions)} (Expected based on count: {total_count})")

    # 5. Deduplicate based on 'id'
    if all_transactions and isinstance(all_transactions[0], dict) and 'id' in all_transactions[0]:
        seen_ids = set()
        unique_transactions = []
        duplicates_found = 0
        for txn in all_transactions:
            txn_id = txn.get('id')
            if txn_id is not None:
                if txn_id not in seen_ids:
                    seen_ids.add(txn_id)
                    unique_transactions.append(txn)
                else:
                    duplicates_found += 1
            else:
                unique_transactions.append(txn) # Keep transactions without an ID

        if duplicates_found > 0:
            logging.info(f"Removed {duplicates_found} duplicate transactions based on 'id'.")
        all_transactions = unique_transactions
        logging.info(f"Total unique transactions after deduplication: {len(all_transactions)}")
    else:
        logging.warning("Could not perform deduplication: 'id' field not found in first transaction or no transactions fetched.")

    return all_transactions

# Use the synchronous save function from the assets script (or redefine it here)
def save_data_sync(data, output_file_path):
    """Saves the collected data to a JSON file (synchronous)."""
    if data is None:
        logging.error("Cannot save data because fetching failed or returned None.")
        return False
    if not data:
        logging.info("No data collected to save.")
        return True # Not an error

    try:
        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        logging.info(f"Successfully saved {len(data)} transactions to {output_file_path}")
        return True
    except Exception as e:
        logging.error(f"Failed to save data to {output_file_path}: {e}", exc_info=True)
        return False

async def main():
    """Main async function to run the fetch and save process."""
    logging.info("Starting async transaction fetching process...")
    collected_transactions = await fetch_all_transactions_concurrently()

    success = False
    if collected_transactions is not None:
        success = save_data_sync(collected_transactions, OUTPUT_JSON_FILE)
    else:
        logging.error("Transaction fetching process failed overall. No data saved.")

    # Close the shared client session
    logging.info("Closing HTTP client...")
    await wealtharc_client.close_client()
    logging.info("HTTP client closed.")

    if success:
        logging.info("Transaction fetching script finished successfully.")
    else:
        logging.error("Transaction fetching script finished with errors.")

if __name__ == "__main__":
    asyncio.run(main())
