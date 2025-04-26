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

OUTPUT_JSON_FILE = "all_positions.json"
PAGE_SIZE = 500 # How many positions to fetch per API call
MAX_ENTRIES_TO_FETCH = 10000 # Maximum number of entries to fetch for this endpoint

async def fetch_position_page(skip: int, top: int) -> list:
    """Fetches a single page of positions asynchronously."""
    logging.debug(f"Requesting positions page: skip={skip}, top={top}")
    try:
        response_data = await wealtharc_client.get_positions(top=top, skip=skip)
        if response_data and isinstance(response_data.get('value'), list):
            logging.info(f"Successfully fetched position page: skip={skip}, count={len(response_data['value'])}")
            return response_data['value']
        else:
            logging.error(f"Failed to fetch or parse position page: skip={skip}. Response: {response_data}")
            return [] # Return empty list on page error
    except Exception as e:
        logging.error(f"Exception fetching position page: skip={skip}. Error: {e}", exc_info=True)
        return [] # Return empty list on exception

async def fetch_all_positions_concurrently():
    """
    Fetches positions from the API concurrently using pagination, up to MAX_ENTRIES_TO_FETCH.
    """
    all_positions = []
    total_count = 0
    target_fetch_count = 0
    num_pages = 0

    # 1. Try to get total count first
    logging.info("Fetching total position count (if available)...")
    try:
        count_response = await wealtharc_client.get_positions(top=0, additional_params={"$count": "true"})
        if count_response and "@odata.count" in count_response:
            total_count = int(count_response["@odata.count"])
            logging.info(f"API reported total position count: {total_count}")
            if total_count == 0:
                logging.info("Total count is 0. No positions to fetch.")
                return []

            # Determine the actual number of entries to fetch based on the limit
            target_fetch_count = min(total_count, MAX_ENTRIES_TO_FETCH)
            logging.info(f"Will fetch a maximum of {target_fetch_count} positions.")

            num_pages = math.ceil(target_fetch_count / PAGE_SIZE)
            logging.info(f"Calculated pages needed based on target count: {num_pages}")
        else:
            logging.error("Failed to get a valid total count required for concurrent fetching. Aborting.")
            return None

    except Exception as e:
        logging.error(f"Error fetching total position count: {e}. Aborting fetch.", exc_info=True)
        return None

    if target_fetch_count == 0:
         logging.info("Target fetch count is 0. No positions to fetch.")
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
        task = fetch_position_page(skip=skip, top=current_top)
        tasks.append(task)

    # 3. Run tasks concurrently and gather results
    logging.info(f"Starting concurrent fetch of {len(tasks)} position pages...")
    results_list_of_lists = await asyncio.gather(*tasks)

    # 4. Flatten the results
    for page_result in results_list_of_lists:
        if page_result:
            all_positions.extend(page_result)

    logging.info(f"Finished fetching. Total positions collected: {len(all_positions)} (Target was: {target_fetch_count})")

    # 5. Truncate if collected more than MAX_ENTRIES_TO_FETCH
    if len(all_positions) > MAX_ENTRIES_TO_FETCH:
        logging.warning(f"Collected {len(all_positions)} positions, exceeding limit. Truncating to {MAX_ENTRIES_TO_FETCH}.")
        all_positions = all_positions[:MAX_ENTRIES_TO_FETCH]

    # 6. Deduplicate based on 'id' (Adjust if the unique identifier is different)
    unique_key = 'id' # Assuming 'id' is the unique key for positions
    if all_positions and isinstance(all_positions[0], dict) and unique_key in all_positions[0]:
        seen_keys = set()
        unique_positions = []
        duplicates_found = 0
        for position in all_positions:
            key_value = position.get(unique_key)
            if key_value is not None:
                # For composite keys, you might need to create a tuple: e.g., (pos.get('portfolioId'), pos.get('assetId'), pos.get('date'))
                if key_value not in seen_keys:
                    seen_keys.add(key_value)
                    unique_positions.append(position)
                else:
                    duplicates_found += 1
            else:
                unique_positions.append(position) # Keep items without the key

        if duplicates_found > 0:
            logging.info(f"Removed {duplicates_found} duplicate positions based on '{unique_key}'.")
        all_positions = unique_positions
        logging.info(f"Total unique positions after deduplication: {len(all_positions)}")
    else:
        logging.info(f"Could not perform deduplication: '{unique_key}' field not found or no positions fetched.")

    return all_positions

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
        logging.info(f"Successfully saved {len(data)} positions to {output_file_path}")
        return True
    except Exception as e:
        logging.error(f"Failed to save data to {output_file_path}: {e}", exc_info=True)
        return False

async def main():
    """Main async function to run the fetch and save process."""
    logging.info("Starting async position fetching process...")
    collected_positions = await fetch_all_positions_concurrently()

    success = False
    if collected_positions is not None:
        success = save_data_sync(collected_positions, OUTPUT_JSON_FILE)
    else:
        logging.error("Position fetching process failed overall. No data saved.")

    logging.info("Closing HTTP client...")
    await wealtharc_client.close_client()
    logging.info("HTTP client closed.")

    if success:
        logging.info("Position fetching script finished successfully.")
    else:
        logging.error("Position fetching script finished with errors.")

if __name__ == "__main__":
    asyncio.run(main())
