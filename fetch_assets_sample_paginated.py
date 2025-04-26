import json
import logging
import time
import wealtharc_client # Import the updated client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

OUTPUT_JSON_FILE = "sample_assets_2k.json" # New output file name
PAGE_SIZE = 200 # Use a smaller page size
TARGET_RECORDS = 2000 # Target number of records to fetch

def fetch_assets_sample_paginated(target_records: int):
    """
    Fetches a sample of assets from the API using pagination,
    stopping after reaching the target number of records.
    """
    all_assets = []
    current_skip = 0
    fetch_more = True
    page_num = 1

    logging.info(f"Starting paginated fetch for Assets sample (target={target_records}) with page size {PAGE_SIZE}...")

    while fetch_more:
        # Determine how many to fetch in this request
        remaining_needed = target_records - len(all_assets)
        current_top = min(PAGE_SIZE, remaining_needed)
        if current_top <= 0:
             fetch_more = False
             break

        logging.info(f"Fetching page {page_num} (skip={current_skip}, top={current_top})...")
        try:
            # Use the get_assets function from the client
            response_data = wealtharc_client.get_assets(top=current_top, skip=current_skip)

            if response_data and isinstance(response_data.get('value'), list):
                assets_page = response_data['value']
                if assets_page:
                    all_assets.extend(assets_page)
                    logging.info(f"Fetched {len(assets_page)} assets on page {page_num}. Total fetched: {len(all_assets)}")

                    # Check if we've fetched enough records or if it was the last page from API
                    if len(all_assets) >= target_records:
                        fetch_more = False
                        logging.info(f"Reached target of {target_records} records.")
                    elif len(assets_page) < current_top:
                        fetch_more = False
                        logging.info("API returned fewer records than requested, assuming end of data.")
                    else:
                        # Continue to next page
                        current_skip += current_top
                        page_num += 1
                        time.sleep(0.5) # Add delay
                else:
                    fetch_more = False
                    logging.info("Received empty 'value' array. No more assets to fetch.")
            else:
                logging.error(f"Failed to fetch or parse page {page_num}. Response: {response_data}")
                fetch_more = False
                all_assets = None

        except Exception as e:
            logging.error(f"An unexpected error occurred during fetch for page {page_num}: {e}")
            fetch_more = False
            all_assets = None

    return all_assets

def save_data(data, output_file_path):
    """Saves the collected data to a JSON file."""
    if data is None:
        logging.error("Cannot save data because fetching failed.")
        return

    try:
        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        logging.info(f"Successfully saved {len(data)} assets to {output_file_path}")
    except Exception as e:
        logging.error(f"Failed to save data to {output_file_path}: {e}")

if __name__ == "__main__":
    collected_assets = fetch_assets_sample_paginated(TARGET_RECORDS) # Pass target
    if collected_assets is not None:
        save_data(collected_assets, OUTPUT_JSON_FILE)
    else:
        logging.error("Asset sample fetching process failed. No data saved.")

    logging.info("Asset sample fetching script finished.")
