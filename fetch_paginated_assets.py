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

OUTPUT_JSON_FILE = "all_assets.json"
PAGE_SIZE = 500 # How many assets to fetch per API call
MAX_ENTRIES_TO_FETCH = 10000 # Maximum number of entries to fetch for this endpoint

async def fetch_asset_page(skip: int, top: int) -> list:
    """Fetches a single page of assets asynchronously."""
    logging.debug(f"Requesting assets page: skip={skip}, top={top}")
    try:
        response_data = await wealtharc_client.get_assets(top=top, skip=skip)
        if response_data and isinstance(response_data.get('value'), list):
            logging.info(f"Successfully fetched asset page: skip={skip}, count={len(response_data['value'])}")
            return response_data['value']
        else:
            logging.error(f"Failed to fetch or parse asset page: skip={skip}. Response: {response_data}")
            return [] # Return empty list on page error
    except Exception as e:
        logging.error(f"Exception fetching asset page: skip={skip}. Error: {e}", exc_info=True)
        return [] # Return empty list on exception

async def fetch_all_assets_concurrently():
    """
    Fetches assets from the API concurrently using pagination, up to MAX_ENTRIES_TO_FETCH.
    """
    all_assets = []
    total_count = 0
    target_fetch_count = 0
    num_pages = 0

    # 1. Try to get total count first
    logging.info("Fetching total asset count (if available)...")
    try:
        count_response = await wealtharc_client.get_assets(top=0, additional_params={"$count": "true"})
        if count_response and "@odata.count" in count_response:
            total_count = int(count_response["@odata.count"])
            logging.info(f"API reported total asset count: {total_count}")
            if total_count == 0:
                logging.info("Total count is 0. No assets to fetch.")
                return []

            # Determine the actual number of entries to fetch based on the limit
            target_fetch_count = min(total_count, MAX_ENTRIES_TO_FETCH)
            logging.info(f"Will fetch a maximum of {target_fetch_count} assets.")

            num_pages = math.ceil(target_fetch_count / PAGE_SIZE)
            logging.info(f"Calculated pages needed based on target count: {num_pages}")
        else:
            logging.error("Failed to get a valid total count required for concurrent fetching. Aborting.")
            # If count is crucial for limiting, abort if not available.
            # Alternative: Fetch sequentially and stop at MAX_ENTRIES_TO_FETCH (less efficient).
            return None

    except Exception as e:
        logging.error(f"Error fetching total asset count: {e}. Aborting fetch.", exc_info=True)
        return None

    if target_fetch_count == 0:
         logging.info("Target fetch count is 0. No assets to fetch.")
         return []

    # 2. Create tasks for the required pages
    tasks = []
    logging.info(f"Preparing {num_pages} tasks for concurrent fetching...")
    for i in range(num_pages):
        skip = i * PAGE_SIZE
        # Adjust top for the last page if it exceeds target_fetch_count
        remaining_to_fetch = target_fetch_count - (i * PAGE_SIZE)
        current_top = min(PAGE_SIZE, remaining_to_fetch)
        if current_top <= 0: # Should not happen with ceil calculation, but safety check
            break
        task = fetch_asset_page(skip=skip, top=current_top)
        tasks.append(task)

    # 3. Run tasks concurrently and gather results
    logging.info(f"Starting concurrent fetch of {len(tasks)} asset pages...")
    results_list_of_lists = await asyncio.gather(*tasks)

    # 4. Flatten the results and check for errors
    failed_pages = 0
    for page_result in results_list_of_lists:
        if page_result: # Check if page fetch returned data
            all_assets.extend(page_result)
        # Note: fetch_asset_page returns [] on error, so critical failures aren't easily tracked here unless it returns None

    logging.info(f"Finished fetching. Total assets collected: {len(all_assets)} (Target was: {target_fetch_count})")

    # 5. Truncate if collected more than MAX_ENTRIES_TO_FETCH (shouldn't happen with adjusted 'top', but safety)
    if len(all_assets) > MAX_ENTRIES_TO_FETCH:
        logging.warning(f"Collected {len(all_assets)} assets, exceeding limit. Truncating to {MAX_ENTRIES_TO_FETCH}.")
        all_assets = all_assets[:MAX_ENTRIES_TO_FETCH]

    # 6. Deduplicate based on 'id' (Optional but good practice if IDs exist and are unique)
    if all_assets and isinstance(all_assets[0], dict) and 'id' in all_assets[0]:
        seen_ids = set()
        unique_assets = []
        duplicates_found = 0
        for asset in all_assets:
            asset_id = asset.get('id')
            if asset_id is not None:
                if asset_id not in seen_ids:
                    seen_ids.add(asset_id)
                    unique_assets.append(asset)
                else:
                    duplicates_found += 1
            else:
                unique_assets.append(asset) # Keep assets without an ID

        if duplicates_found > 0:
            logging.info(f"Removed {duplicates_found} duplicate assets based on 'id'.")
        all_assets = unique_assets
        logging.info(f"Total unique assets after deduplication: {len(all_assets)}")
    else:
        logging.info("Could not perform deduplication: 'id' field not found or no assets fetched.")

    return all_assets

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
        logging.info(f"Successfully saved {len(data)} assets to {output_file_path}")
        return True
    except Exception as e:
        logging.error(f"Failed to save data to {output_file_path}: {e}", exc_info=True)
        return False

async def main():
    """Main async function to run the fetch and save process."""
    logging.info("Starting async asset fetching process...")
    collected_assets = await fetch_all_assets_concurrently()

    success = False
    if collected_assets is not None:
        success = save_data_sync(collected_assets, OUTPUT_JSON_FILE)
    else:
        logging.error("Asset fetching process failed overall. No data saved.")

    # Close the shared client session (assuming it's managed globally or passed)
    # If the client is module-level in wealtharc_client, close it once at the end of all scripts.
    # For standalone script, close it here.
    logging.info("Closing HTTP client...")
    await wealtharc_client.close_client()
    logging.info("HTTP client closed.")

    if success:
        logging.info("Asset fetching script finished successfully.")
    else:
        logging.error("Asset fetching script finished with errors.")

if __name__ == "__main__":
    asyncio.run(main())
