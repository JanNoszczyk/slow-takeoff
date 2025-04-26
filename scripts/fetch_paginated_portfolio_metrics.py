import json
import logging
import math
import asyncio
import wealtharc_client # Import the async client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
# Reduce httpx INFO logs if too noisy
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

OUTPUT_JSON_FILE = "all_portfolio_metrics.json"
PAGE_SIZE = 500 # How many metrics entries to fetch per API call
MAX_ENTRIES_TO_FETCH = 10000 # Maximum number of entries to fetch for this endpoint

async def fetch_metrics_page(skip: int, top: int) -> list:
    """Fetches a single page of portfolio daily metrics asynchronously."""
    logging.debug(f"Requesting portfolio metrics page: skip={skip}, top={top}")
    try:
        # Use the correct client function: get_portfolios_daily_metrics
        response_data = await wealtharc_client.get_portfolios_daily_metrics(top=top, skip=skip)
        if response_data and isinstance(response_data.get('value'), list):
            logging.info(f"Successfully fetched portfolio metrics page: skip={skip}, count={len(response_data['value'])}")
            return response_data['value']
        else:
            logging.error(f"Failed to fetch or parse portfolio metrics page: skip={skip}. Response: {response_data}")
            return [] # Return empty list on page error
    except Exception as e:
        logging.error(f"Exception fetching portfolio metrics page: skip={skip}. Error: {e}", exc_info=True)
        return [] # Return empty list on exception

async def fetch_all_portfolio_metrics_concurrently():
    """
    Fetches portfolio daily metrics from the API concurrently using pagination, up to MAX_ENTRIES_TO_FETCH.
    """
    all_metrics = []
    total_count = 0
    target_fetch_count = 0
    num_pages = 0

    # 1. Try to get total count first
    logging.info("Fetching total portfolio metrics count (if available)...")
    try:
        # Use the correct client function
        count_response = await wealtharc_client.get_portfolios_daily_metrics(top=0, additional_params={"$count": "true"})
        if count_response and "@odata.count" in count_response:
            total_count = int(count_response["@odata.count"])
            logging.info(f"API reported total portfolio metrics count: {total_count}")
            if total_count == 0:
                logging.info("Total count is 0. No portfolio metrics to fetch.")
                return []

            # Determine the actual number of entries to fetch based on the limit
            target_fetch_count = min(total_count, MAX_ENTRIES_TO_FETCH)
            logging.info(f"Will fetch a maximum of {target_fetch_count} portfolio metrics entries.")

            num_pages = math.ceil(target_fetch_count / PAGE_SIZE)
            logging.info(f"Calculated pages needed based on target count: {num_pages}")
        else:
            logging.error("Failed to get a valid total count required for concurrent fetching. Aborting.")
            return None

    except Exception as e:
        logging.error(f"Error fetching total portfolio metrics count: {e}. Aborting fetch.", exc_info=True)
        return None

    if target_fetch_count == 0:
         logging.info("Target fetch count is 0. No portfolio metrics to fetch.")
         return []

    # 2. Create tasks for the required pages
    tasks = []
    logging.info(f"Preparing {num_pages} tasks for concurrent fetching...")
    for i in range(num_pages):
        skip = i * PAGE_SIZE
        remaining_to_fetch = target_fetch_count - (i * PAGE_SIZE)
        current_top = min(PAGE_SIZE, remaining_to_fetch)
        if current_top <= 0:
            break
        task = fetch_metrics_page(skip=skip, top=current_top)
        tasks.append(task)

    # 3. Run tasks concurrently and gather results
    logging.info(f"Starting concurrent fetch of {len(tasks)} portfolio metrics pages...")
    results_list_of_lists = await asyncio.gather(*tasks)

    # 4. Flatten the results
    for page_result in results_list_of_lists:
        if page_result:
            all_metrics.extend(page_result)

    logging.info(f"Finished fetching. Total portfolio metrics entries collected: {len(all_metrics)} (Target was: {target_fetch_count})")

    # 5. Truncate if collected more than MAX_ENTRIES_TO_FETCH
    if len(all_metrics) > MAX_ENTRIES_TO_FETCH:
        logging.warning(f"Collected {len(all_metrics)} metrics entries, exceeding limit. Truncating to {MAX_ENTRIES_TO_FETCH}.")
        all_metrics = all_metrics[:MAX_ENTRIES_TO_FETCH]

    # 6. Deduplicate (Optional - Define the unique key(s) for metrics if needed)
    # Example: Assuming a composite key of portfolioId and date
    unique_key_tuple = ('portfolioId', 'date') # Adjust as necessary
    if all_metrics and isinstance(all_metrics[0], dict) and all(k in all_metrics[0] for k in unique_key_tuple):
        seen_keys = set()
        unique_metrics = []
        duplicates_found = 0
        for metric in all_metrics:
            key_value = tuple(metric.get(k) for k in unique_key_tuple)
            if all(v is not None for v in key_value): # Ensure all parts of the key are present
                if key_value not in seen_keys:
                    seen_keys.add(key_value)
                    unique_metrics.append(metric)
                else:
                    duplicates_found += 1
            else:
                unique_metrics.append(metric) # Keep items with missing key components

        if duplicates_found > 0:
            logging.info(f"Removed {duplicates_found} duplicate metrics entries based on {unique_key_tuple}.")
        all_metrics = unique_metrics
        logging.info(f"Total unique metrics entries after deduplication: {len(all_metrics)}")
    else:
        logging.info(f"Could not perform deduplication: Key fields {unique_key_tuple} not found or no metrics fetched.")


    return all_metrics

def save_data_sync(data, output_file_path):
    """Saves the collected data to a JSON file (synchronous)."""
    if data is None:
        logging.error("Cannot save data because fetching failed or returned None.")
        return False
    if not data:
        logging.info("No data collected to save.")
        return True

    try:
        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        logging.info(f"Successfully saved {len(data)} portfolio metrics entries to {output_file_path}")
        return True
    except Exception as e:
        logging.error(f"Failed to save data to {output_file_path}: {e}", exc_info=True)
        return False

async def main():
    """Main async function to run the fetch and save process."""
    logging.info("Starting async portfolio metrics fetching process...")
    collected_metrics = await fetch_all_portfolio_metrics_concurrently()

    success = False
    if collected_metrics is not None:
        success = save_data_sync(collected_metrics, OUTPUT_JSON_FILE)
    else:
        logging.error("Portfolio metrics fetching process failed overall. No data saved.")

    # NOTE: Closing the client here assumes this is the last script run.
    # If running multiple scripts sequentially, close the client only after the last one.
    logging.info("Closing HTTP client...")
    await wealtharc_client.close_client()
    logging.info("HTTP client closed.")

    if success:
        logging.info("Portfolio metrics fetching script finished successfully.")
    else:
        logging.error("Portfolio metrics fetching script finished with errors.")

if __name__ == "__main__":
    asyncio.run(main())
