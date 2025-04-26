import json
import logging
import re
import csv
from typing import List, Dict, Any, Optional, Set

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

INPUT_ASSETS_JSON = "sample_assets_2k.json" # Changed input source
INPUT_TRANSACTIONS_JSON = "sample_transactions_2k.json" # Changed input source
OUTPUT_CSV_FILE = "public_entity_transactions.csv"

# Transaction types considered relevant for public entity trading
RELEVANT_TRANSACTION_TYPES: Set[str] = {
    "Buy", "Sell", "Subscription", "Redemption", "Exchange", "Merger",
    "Split", "SpinOff", "OpenLongPosition", "OpenShortPosition",
    "CorporateAction" # Adding CorporateAction as potentially relevant
}

def load_json_data(json_file_path: str) -> Optional[List[Dict[str, Any]]]:
    """Loads a list of records directly from a JSON file."""
    # Removed extra """ here
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                logging.info(f"Successfully loaded {len(data)} records from {json_file_path}")
                return data
            else:
                logging.error(f"Loaded JSON from {json_file_path} is not a list.")
                return None
    except FileNotFoundError:
        logging.error(f"Input JSON file not found: {json_file_path}")
        return None
    except json.JSONDecodeError as e:
        logging.error(f"Failed to decode JSON from {json_file_path}: {e}")
        return None
    except Exception as e:
        logging.error(f"An error occurred reading the JSON file {json_file_path}: {e}")
        return None # Return None on error, consistent with other error paths


def analyze_and_export(assets: List[Dict[str, Any]], transactions: List[Dict[str, Any]], output_csv_path: str):
    """
    Analyzes assets and transactions, filters relevant data, and exports to CSV.
    """
    if not assets:
        logging.warning("No Assets data provided.")
    if not transactions:
        logging.warning("No Transactions data provided.")
        # Decide if we should still create an empty CSV or return

    # 1. Create a map of asset_id -> {isin, name} for instruments with ISINs
    instrument_map: Dict[int, Dict[str, str]] = {}
    instruments_with_isin_count = 0
    for asset in assets:
        if (isinstance(asset, dict) and
            asset.get('@odata.type') == '#WealthArc.Instrument' and
            asset.get('id') is not None and
            asset.get('isin')):
            instrument_map[asset['id']] = {
                "isin": asset['isin'],
                "name": asset.get('name', 'N/A') # Use N/A if name is missing
            }
            instruments_with_isin_count += 1
    logging.info(f"Created map for {instruments_with_isin_count} instruments with ISINs from the assets sample.")
    if not instrument_map:
         logging.warning("No instruments with ISIN found in the Assets sample. CSV will likely be empty.")
         # Still proceed to create empty CSV if needed

    # 2. Filter transactions and combine with asset info
    output_data: List[Dict[str, Any]] = []
    relevant_transactions_count = 0
    for tx in transactions:
        if not isinstance(tx, dict):
            continue

        asset_id = tx.get('assetId')
        tx_type = tx.get('type')

        # Check if transaction type is relevant and if the asset is a known instrument with an ISIN
        if tx_type in RELEVANT_TRANSACTION_TYPES and asset_id in instrument_map:
            asset_info = instrument_map[asset_id]
            output_data.append({
                "transaction_id": tx.get('id'),
                "asset_id": asset_id,
                "asset_isin": asset_info['isin'],
                "asset_name": asset_info['name'],
                "transaction_type": tx_type,
                "transaction_date": tx.get('transactionDate'),
                "value_date": tx.get('valueDate'),
                "quantity": tx.get('quantity'),
                "price": tx.get('price'),
                "price_currency": tx.get('priceCurrency'),
                "portfolio_id": tx.get('portfolioId'),
            })
            relevant_transactions_count += 1

    logging.info(f"Found {relevant_transactions_count} relevant transactions involving instruments with ISINs.")

    # 3. Write to CSV
    if not output_data:
        logging.warning("No data to write to CSV.")
        # Create empty CSV with headers?
        fieldnames = [
            "transaction_id", "asset_id", "asset_isin", "asset_name",
            "transaction_type", "transaction_date", "value_date",
            "quantity", "price", "price_currency", "portfolio_id"
        ]
        try:
             with open(output_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
             logging.info(f"Created empty CSV file with headers: {output_csv_path}")
        except Exception as e:
             logging.error(f"Failed to write empty CSV header: {e}")
        return

    fieldnames = list(output_data[0].keys()) # Get headers from the first record
    try:
        with open(output_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(output_data)
        logging.info(f"Successfully wrote {len(output_data)} relevant transaction records to {output_csv_path}")
    except Exception as e:
        logging.error(f"Failed to write data to CSV {output_csv_path}: {e}")


if __name__ == "__main__":
    logging.info(f"Loading data from {INPUT_ASSETS_JSON} and {INPUT_TRANSACTIONS_JSON}...")
    assets_data = load_json_data(INPUT_ASSETS_JSON)
    transactions_data = load_json_data(INPUT_TRANSACTIONS_JSON)

    if assets_data is not None and transactions_data is not None:
        analyze_and_export(assets_data, transactions_data, OUTPUT_CSV_FILE)
    else:
        logging.error("Failed to load necessary data from JSON files. Analysis aborted.")

    logging.info("Analysis script finished.")
