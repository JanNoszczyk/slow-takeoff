import json
import logging
import re

# Configure logging for this script
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

INPUT_JSON_FILE = "all_assets.json" # Changed from INPUT_LOG_FILE
OUTPUT_JSON_FILE = "filtered_assets.json"

def load_json_data(json_file_path):
    """Loads JSON data directly from a file."""
    # Removed extra """ here
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # The paginated script saves the list directly, not nested under 'value'
            if isinstance(data, list):
                return data
            # Handle case if it was saved nested (less likely with current fetch script)
            elif isinstance(data, dict) and 'value' in data and isinstance(data['value'], list):
                 logging.warning("Loaded data was nested under 'value', using that.")
                 return data['value']
            else:
                logging.error("Loaded JSON is not a list or a dict with a 'value' list.")
                return None
    except FileNotFoundError:
        logging.error(f"Input JSON file not found: {json_file_path}")
        return None
    except json.JSONDecodeError as e:
        logging.error(f"Failed to decode JSON from {json_file_path}: {e}")
        return None
    except Exception as e:
        logging.error(f"An error occurred reading the JSON file: {e}")
        return None

def process_assets(all_assets_list):
    """
    Filters a list of assets to find Instruments with an ISIN and extracts relevant fields.
    """
    filtered_instruments = []
    if not isinstance(all_assets_list, list):
        logging.error("Invalid input: process_assets expects a list.")
        return filtered_instruments

    for asset in all_assets_list:
        # Check if it's an Instrument (dict) and has a non-empty ISIN
        if (isinstance(asset, dict) and
            asset.get('@odata.type') == '#WealthArc.Instrument' and
            asset.get('isin')): # Checks for non-null and non-empty string

            filtered_instruments.append({
                "id": asset.get('id'),
                "isin": asset.get('isin'),
                "name": asset.get('name')
            })
        # Optional: Log if it's a CashAccount or Instrument without ISIN?
        # elif asset.get('@odata.type') == '#WealthArc.CashAccount':
        #     logging.debug(f"Skipping CashAccount with id {asset.get('id')}")
        # elif asset.get('@odata.type') == '#WealthArc.Instrument' and not asset.get('isin'):
        #      logging.debug(f"Skipping Instrument without ISIN: id {asset.get('id')}, name {asset.get('name')}")


    logging.info(f"Found {len(filtered_instruments)} instruments with ISINs.")
    return filtered_instruments

def save_filtered_data(data, output_file_path):
    """Saves the filtered data to a JSON file."""
    try:
        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        logging.info(f"Successfully saved filtered instruments data to {output_file_path}")
    except Exception as e:
        logging.error(f"Failed to save data to {output_file_path}: {e}")

if __name__ == "__main__":
    logging.info(f"Starting processing of {INPUT_JSON_FILE}...")
    all_assets = load_json_data(INPUT_JSON_FILE) # Load directly from JSON

    if all_assets is not None: # Check if loading was successful
        filtered_data = process_assets(all_assets)
        if filtered_data:
            save_filtered_data(filtered_data, OUTPUT_JSON_FILE)
        else:
            logging.warning("No instruments with ISINs found or extracted.")
    else:
        logging.error("Failed to load asset data from JSON file.")

    logging.info("Asset processing finished.")
