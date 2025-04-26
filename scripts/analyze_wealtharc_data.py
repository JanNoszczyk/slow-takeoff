import pandas as pd
import json
import logging
import argparse # To accept command-line arguments
import os # To manipulate file paths
import re # For potential pattern matching in descriptions
import io  # For capturing df.info() output
import sys # To write to stdout or file

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stderr) # Log to stderr

def load_and_save_csv(json_filepath):
    """Loads data from a JSON file, saves it as CSV, and returns a pandas DataFrame."""
    logging.info(f"Processing {json_filepath}...")
    if not os.path.exists(json_filepath):
        logging.error(f"Error: File not found at {json_filepath}")
        return None, None

    # Generate CSV filepath
    base_name = os.path.basename(json_filepath)
    csv_filename = os.path.splitext(base_name)[0] + '.csv'
    csv_filepath = os.path.join(os.path.dirname(json_filepath), csv_filename) # Save in the same directory

    logging.info(f"Loading data from {json_filepath}...")
    try:
        with open(json_filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not data:
            logging.warning(f"JSON file {json_filepath} is empty.")
            return pd.DataFrame(), csv_filepath # Return empty DataFrame

        # Normalize the data if it's nested (common for API responses)
        df = pd.json_normalize(data)
        logging.info(f"Successfully loaded data from {json_filepath}. Shape: {df.shape}")

        # Save to CSV
        try:
            df.to_csv(csv_filepath, index=False, encoding='utf-8')
            logging.info(f"Successfully saved data to {csv_filepath}")
        except Exception as e:
            logging.error(f"Failed to save data to {csv_filepath}. Error: {e}", exc_info=True)
            # Continue with analysis even if saving failed, but log the error

        return df, csv_filepath

    except json.JSONDecodeError:
        logging.error(f"Error: Could not decode JSON from {json_filepath}")
        return None, None
    except Exception as e:
        logging.error(f"An unexpected error occurred during loading/saving {json_filepath}: {e}", exc_info=True)
        return None, None

def write_markdown(f, content):
    """Helper to write content to the file handle."""
    f.write(content + "\n")

def analyze_data(df, data_type, base_output_name, md_file_handle):
    """
    Performs analysis tailored to the data type, identifies public entities,
    and writes results to the markdown file handle.
    """
    f = md_file_handle # Use the passed file handle

    if df is None or df.empty:
        logging.warning(f"DataFrame for {data_type} is empty or None. Skipping analysis.")
        write_markdown(f, f"\n## Analysis Results for `{base_output_name}.csv` (Data Type: {data_type.capitalize()})\n")
        write_markdown(f, f"*Skipping analysis as DataFrame for {data_type} is empty or None.*\n")
        return

    logging.info(f"Starting analysis for {data_type}...")
    write_markdown(f, f"\n## Analysis Results for `{base_output_name}.csv` (Data Type: {data_type.capitalize()})\n")

    # --- DataFrame Info ---
    write_markdown(f, "### DataFrame Info\n")
    buffer = io.StringIO()
    try:
        with pd.option_context('display.max_info_columns', 200):
             df.info(buf=buffer)
        info_str = buffer.getvalue()
        write_markdown(f, f"```\n{info_str}\n```\n")
    except Exception as e:
        logging.error(f"Error getting df.info() for {data_type}: {e}")
        write_markdown(f, "*Error generating DataFrame info.*\n")


    # --- First 5 Rows ---
    write_markdown(f, "### First 5 Rows\n")
    try:
        write_markdown(f, df.head().to_markdown(index=False, numalign="left", stralign="left") + "\n")
    except Exception as e:
        logging.error(f"Error generating head markdown for {data_type}: {e}")
        write_markdown(f, "*Error displaying first 5 rows.*\n")

    # --- Define Data Type Specific Keys ---
    key_config = {
        'assets': {
            'potential_keys': ['assetClass', 'assetSubClass', 'investmentType', 'currency.code', 'country.name', 'sector', 'instrumentIssuer.name', 'name', 'isin', 'ric', 'wkn', 'cusip', 'region', 'industryGroup', 'industry', 'subIndustry'],
            'identifier_cols': ['isin', 'ric', 'cusip', 'wkn', 'symbol', 'ticker'],
            'name_cols': ['name', 'instrumentIssuer.name'],
            'base_info_cols': ['name', 'assetClass', 'assetSubClass', 'investmentType', 'instrumentIssuer.name'],
            'numeric_cols': ['quotationFactor', 'interestRate', 'riskScore', 'strikePrice', 'multiplier', 'suitabilityScore', 'appropriatenessScore']
        },
        'transactions': {
            'potential_keys': ['type', 'status', 'currency.code', 'asset.assetClass', 'asset.name', 'portfolio.name', 'description'],
            'identifier_cols': ['asset.isin', 'asset.ric', 'asset.cusip', 'asset.wkn', 'asset.symbol', 'asset.ticker'],
            'name_cols': ['asset.name', 'description'],
            'base_info_cols': ['id', 'date', 'type', 'status', 'quantity', 'price', 'amount', 'asset.name', 'description'],
            'numeric_cols': ['quantity', 'price', 'fxRate', 'referencedInstrumentId', 'referencedInstrumentQuantity', 'interest', 'amount']
        },
        'positions': {
            'potential_keys': ['portfolio.name', 'asset.assetClass', 'asset.name', 'asset.currency.code'],
            'identifier_cols': ['asset.isin', 'asset.ric', 'asset.cusip', 'asset.wkn', 'asset.symbol', 'asset.ticker'],
            'name_cols': ['asset.name'],
            'base_info_cols': ['portfolio.name', 'asset.name', 'quantity', 'marketValue', 'asset.assetClass'],
            'numeric_cols': ['quantity', 'price', 'unitCostInPriceCurrency', 'allocation', 'bookCostInPortfolioCurrency', 'fxRate', 'accruedInterestInPortfolioCurrency', 'accruedInterestInPriceCurrency', 'marketValue']
        },
        'portfolios': {
            'potential_keys': ['name', 'status', 'currency.code', 'type', 'custodian.name', 'mandateType'],
            'identifier_cols': [],
            'name_cols': ['name', 'custodian.name'],
            'base_info_cols': ['id', 'name', 'status', 'currency.code', 'type', 'custodian.name', 'mandateType'],
            'numeric_cols': ['parentPortfolioId', 'modelPortfolioId']
        },
        'portfolio_metrics': {
            'potential_keys': ['portfolio.name', 'currency.code'],
            'identifier_cols': [],
            'name_cols': ['portfolio.name'],
            'base_info_cols': ['portfolio.name', 'date', 'marketValue', 'nav', 'performance', 'overdraftsCount'],
            'numeric_cols': ['marketValue', 'nav', 'performance', 'contribution', 'withdrawal', 'managementFees', 'custodyFees', 'otherFees', 'dividends', 'interests', 'realisedGainLoss', 'unrealisedGainLoss', 'overdraftsCount']
        }
    }

    config = key_config.get(data_type, key_config['assets'])
    potential_keys = config['potential_keys']
    identifier_cols = config['identifier_cols']
    name_cols = config['name_cols']
    base_info_cols = config['base_info_cols']
    numeric_cols = config['numeric_cols']

    # --- Value Counts ---
    write_markdown(f, "### Value Counts for Key Columns (Top 20)\n")
    for key in potential_keys:
        if key in df.columns:
            try:
                counts = df[key].astype(str).value_counts()
                if not counts.empty:
                    write_markdown(f, f"#### Value Counts for `{key}`\n")
                    write_markdown(f, counts.head(20).to_markdown(numalign="left", stralign="left") + "\n")
                else:
                    logging.info(f"Column '{key}' has no values to count for {data_type}.")
            except Exception as e:
                logging.error(f"Could not get value counts for column '{key}' in {data_type}. Error: {e}")
                write_markdown(f, f"*Error getting value counts for `{key}`.*\n")
        else:
            logging.debug(f"Column '{key}' not found in DataFrame for {data_type}.")

    # --- Summary Statistics for Numeric Columns ---
    write_markdown(f, "### Summary Statistics for Numeric Columns\n")
    available_numeric = [col for col in numeric_cols if col in df.columns]
    available_numeric = [col for col in available_numeric if pd.api.types.is_numeric_dtype(df[col])]

    if available_numeric:
        try:
            summary_stats = df[available_numeric].describe()
            write_markdown(f, summary_stats.to_markdown(floatfmt=".2f") + "\n")
        except Exception as e:
            logging.error(f"Error generating summary stats for {data_type}: {e}")
            write_markdown(f, "*Error generating summary statistics.*\n")
    else:
        write_markdown(f, "*No relevant numeric columns found for summary statistics.*\n")


    # --- Public Entity Identification ---
    write_markdown(f, f"### Potential Public Entity Identification\n")
    available_identifiers = [col for col in identifier_cols if col in df.columns]
    available_names = [col for col in name_cols if col in df.columns]
    available_base_info = [col for col in base_info_cols if col in df.columns]

    identifier_mask = pd.Series(False, index=df.index)
    if available_identifiers:
        try:
            identifier_mask = df[available_identifiers].notna().any(axis=1)
        except Exception as e:
             logging.error(f"Error creating identifier mask for {data_type}: {e}")

    name_mask = pd.Series(False, index=df.index)
    frequent_names = set()
    min_frequency = 3
    if available_names:
        for name_col in available_names:
            try:
                name_counts = df[name_col].astype(str).value_counts()
                frequent_names.update(name_counts[name_counts >= min_frequency].index.tolist())
            except Exception as e:
                logging.warning(f"Could not analyze frequency for name column '{name_col}' in {data_type}. Error: {e}")
        if frequent_names:
            for name_col in available_names:
                try:
                    name_mask |= df[name_col].astype(str).isin(frequent_names)
                except Exception as e:
                    logging.warning(f"Error creating name mask for column '{name_col}' in {data_type}. Error: {e}")

    combined_mask = identifier_mask | name_mask

    if combined_mask.any():
        cols_to_select = list(set(available_base_info + available_identifiers + available_names))
        cols_to_select = [col for col in cols_to_select if col in df.columns]

        try:
            potential_entities_df = df.loc[combined_mask, cols_to_select].copy().drop_duplicates()
            entity_count = len(potential_entities_df)

            logging.info(f"Found {entity_count} potential public entity candidates in {data_type}.")
            write_markdown(f, f"Identified **{entity_count}** potential public entity candidates based on identifiers or name frequency (>= {min_frequency}).\n")
            write_markdown(f, f"#### Potential Public Entities ({data_type.capitalize()}, Top 20)\n")
            write_markdown(f, potential_entities_df.head(20).to_markdown(index=False, numalign="left", stralign="left") + "\n")

            output_entities_csv = f"{base_output_name}_public_entities.csv"
            try:
                potential_entities_df.to_csv(output_entities_csv, index=False, encoding='utf-8')
                logging.info(f"Saved {entity_count} potential public entities to {output_entities_csv}")
                write_markdown(f, f"*Saved {entity_count} candidates to `{output_entities_csv}`.*\n")
            except Exception as e:
                logging.error(f"Failed to save potential public entities for {data_type} to CSV. Error: {e}", exc_info=True)
                write_markdown(f, f"*Error saving potential public entities to `{output_entities_csv}`.*\n")

        except Exception as e:
             logging.error(f"Error processing potential entities for {data_type}: {e}")
             write_markdown(f, "*Error occurred during potential entity identification.*\n")
    else:
        logging.info(f"No potential public entity candidates identified in {data_type} based on current criteria.")
        write_markdown(f, f"*No potential public entity candidates identified based on current criteria (min frequency: {min_frequency}).*\n")


    # --- Aggregations and Further Analysis ---
    write_markdown(f, "### Aggregations and Further Analysis\n")

    # --- Assets ---
    if data_type == 'assets':
        if 'assetClass' in df.columns:
             write_markdown(f, "#### Asset Count per Asset Class\n")
             try:
                 counts = df['assetClass'].astype(str).value_counts().reset_index()
                 counts.columns = ['Asset Class', 'Count']
                 write_markdown(f, counts.to_markdown(index=False, numalign="left", stralign="left") + "\n")
             except Exception as e:
                  logging.error(f"Aggregation error on assetClass for {data_type}: {e}")
                  write_markdown(f, "*Error during aggregation.*\n")
        if 'country.name' in df.columns:
             write_markdown(f, "#### Asset Count per Country (Top 20)\n")
             try:
                 counts = df['country.name'].astype(str).value_counts().reset_index()
                 counts.columns = ['Country', 'Count']
                 write_markdown(f, counts.head(20).to_markdown(index=False, numalign="left", stralign="left") + "\n")
             except Exception as e:
                  logging.error(f"Aggregation error on country.name for {data_type}: {e}")
                  write_markdown(f, "*Error during aggregation.*\n")
        if 'instrumentIssuer.name' in df.columns:
            write_markdown(f, "#### Asset Count per Instrument Issuer (Top 20)\n")
            try:
                issuer_counts = df['instrumentIssuer.name'].astype(str).value_counts().reset_index()
                issuer_counts.columns = ['Instrument Issuer', 'Asset Count']
                issuer_counts = issuer_counts.sort_values(by='Asset Count', ascending=False)
                write_markdown(f, issuer_counts.head(20).to_markdown(index=False, numalign="left", stralign="left") + "\n")
            except Exception as e:
                logging.error(f"Could not perform aggregation on 'instrumentIssuer.name' for {data_type}. Error: {e}")
                write_markdown(f, "*Error during aggregation.*\n")

    # --- Transactions ---
    elif data_type == 'transactions':
         if 'type' in df.columns and 'amount' in df.columns:
              write_markdown(f, "#### Transaction Summary by Type\n")
              try:
                 df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
                 summary = df.groupby('type')['amount'].agg(['count', 'sum', 'mean']).reset_index().dropna(subset=['sum'])
                 summary = summary.sort_values(by='count', ascending=False)
                 write_markdown(f, summary.to_markdown(index=False, floatfmt=".2f") + "\n")
              except Exception as e:
                   logging.error(f"Aggregation error on transaction type/amount for {data_type}: {e}")
                   write_markdown(f, "*Error during aggregation.*\n")
         if 'asset.name' in df.columns:
             write_markdown(f, "#### Transaction Count per Asset Name (Top 20)\n")
             try:
                 asset_txn_counts = df['asset.name'].astype(str).value_counts().reset_index()
                 asset_txn_counts.columns = ['Asset Name', 'Transaction Count']
                 asset_txn_counts = asset_txn_counts.sort_values(by='Transaction Count', ascending=False)
                 write_markdown(f, asset_txn_counts.head(20).to_markdown(index=False, numalign="left", stralign="left") + "\n")
             except Exception as e:
                 logging.error(f"Could not perform aggregation on 'asset.name' for {data_type}. Error: {e}")
                 write_markdown(f, "*Error during aggregation.*\n")
         if 'amount' in df.columns:
              threshold = 1_000_000
              try:
                  df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
                  large_txns = df[df['amount'].abs() > threshold].copy()
                  write_markdown(f, f"#### Large Transactions (Absolute Amount > {threshold:,})\n")
                  if not large_txns.empty:
                      cols = ['id', 'date', 'type', 'amount', 'asset.name', 'description']
                      cols = [c for c in cols if c in large_txns.columns]
                      write_markdown(f, large_txns[cols].head(20).to_markdown(index=False, floatfmt=".2f") + "\n")
                  else:
                      write_markdown(f, f"*No transactions found exceeding the threshold {threshold:,}.*\n")
              except Exception as e:
                   logging.error(f"Error identifying large transactions for {data_type}: {e}")
                   write_markdown(f, "*Error identifying large transactions.*\n")

    # --- Positions ---
    elif data_type == 'positions':
         if 'asset.assetClass' in df.columns and 'marketValue' in df.columns:
              write_markdown(f, "#### Total Market Value by Asset Class\n")
              try:
                  df['marketValue'] = pd.to_numeric(df['marketValue'], errors='coerce')
                  summary = df.groupby('asset.assetClass')['marketValue'].agg(['count', 'sum']).reset_index().dropna(subset=['sum'])
                  summary.columns = ['Asset Class', 'Count', 'Total Market Value']
                  summary = summary.sort_values(by='Total Market Value', ascending=False)
                  write_markdown(f, summary.to_markdown(index=False, floatfmt=".2f") + "\n")
              except Exception as e:
                   logging.error(f"Aggregation error on position assetClass/marketValue for {data_type}: {e}")
                   write_markdown(f, "*Error during aggregation.*\n")
         if 'asset.name' in df.columns:
            write_markdown(f, "#### Position Count per Asset Name (Top 20)\n")
            try:
                asset_pos_counts = df['asset.name'].astype(str).value_counts().reset_index()
                asset_pos_counts.columns = ['Asset Name', 'Position Count']
                asset_pos_counts = asset_pos_counts.sort_values(by='Position Count', ascending=False)
                write_markdown(f, asset_pos_counts.head(20).to_markdown(index=False, numalign="left", stralign="left") + "\n")
            except Exception as e:
                logging.error(f"Could not perform aggregation on 'asset.name' for {data_type}. Error: {e}")
                write_markdown(f, "*Error during aggregation.*\n")

    # --- Portfolios ---
    elif data_type == 'portfolios':
         if 'type' in df.columns:
              write_markdown(f, "#### Portfolio Count by Type\n")
              try:
                  counts = df['type'].astype(str).value_counts().reset_index()
                  counts.columns = ['Type', 'Count']
                  write_markdown(f, counts.to_markdown(index=False) + "\n")
              except Exception as e:
                   logging.error(f"Aggregation error on portfolio type for {data_type}: {e}")
                   write_markdown(f, "*Error during aggregation.*\n")
         if 'custodian.name' in df.columns:
              write_markdown(f, "#### Portfolio Count by Custodian (Top 20)\n")
              try:
                  counts = df['custodian.name'].astype(str).value_counts().reset_index()
                  counts.columns = ['Custodian', 'Count']
                  write_markdown(f, counts.head(20).to_markdown(index=False) + "\n")
              except Exception as e:
                   logging.error(f"Aggregation error on custodian.name for {data_type}: {e}")
                   write_markdown(f, "*Error during aggregation.*\n")

    # --- Portfolio Metrics ---
    elif data_type == 'portfolio_metrics':
         if 'portfolio.name' in df.columns:
             write_markdown(f, "#### Metrics Summary per Portfolio (Aggregated, Top 20 by Entry Count)\n")
             available_numeric_metrics = [col for col in numeric_cols if col in df.columns]
             available_numeric_metrics = [col for col in available_numeric_metrics if pd.api.types.is_numeric_dtype(df[col])]

             if available_numeric_metrics:
                 try:
                     for col in available_numeric_metrics:
                         df[col] = pd.to_numeric(df[col], errors='coerce')

                     agg_metrics = {metric: 'sum' for metric in ['marketValue', 'nav', 'contribution', 'withdrawal', 'managementFees', 'custodyFees', 'otherFees', 'dividends', 'interests', 'realisedGainLoss', 'unrealisedGainLoss'] if metric in available_numeric_metrics}
                     agg_metrics['date'] = 'count' # Count entries

                     if agg_metrics:
                        summary = df.groupby('portfolio.name').agg(agg_metrics).reset_index()
                        summary.rename(columns={'date': 'entry_count'}, inplace=True)
                        agg_cols_only = [col for col in summary.columns if col not in ['portfolio.name', 'entry_count']]
                        summary = summary.dropna(how='all', subset=agg_cols_only)
                        summary = summary.sort_values(by='entry_count', ascending=False)
                        write_markdown(f, summary.head(20).to_markdown(index=False, floatfmt=".2f") + "\n")
                     else:
                         write_markdown(f, "*No relevant numeric metric columns found for sum aggregation.*\n")

                 except Exception as e:
                      logging.error(f"Aggregation error on portfolio metrics for {data_type}: {e}")
                      write_markdown(f, "*Error during aggregation.*\n")
             else:
                  write_markdown(f, "*No numeric metrics columns found for aggregation.*\n")
         else:
              write_markdown(f, "*Portfolio name column not found for metrics aggregation.*\n")

    else:
        write_markdown(f, "*No specific aggregations defined for this data type.*\n")

    logging.info(f"Finished analysis for {data_type}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load WealthArc JSON data, save as CSV, perform analysis, and generate a Markdown report.")
    parser.add_argument("json_filepath", help="Path to the input JSON file (e.g., all_assets.json)")
    parser.add_argument("-o", "--output-file", default="analysis_report.md", help="Path to the output Markdown file (default: analysis_report.md)")
    parser.add_argument("--overwrite", action='store_true', help="Overwrite the output file instead of appending.") # Add overwrite flag
    args = parser.parse_args()

    json_file = args.json_filepath
    output_md_file = args.output_file
    write_mode = 'w' if args.overwrite else 'a' # Determine write mode
    base_name = os.path.basename(json_file)
    base_output_name = os.path.splitext(base_name)[0]

    # Determine data type from filename
    data_type = "unknown"
    if "assets" in base_output_name:
        data_type = "assets"
    elif "transactions" in base_output_name:
        data_type = "transactions"
    elif "positions" in base_output_name:
        data_type = "positions"
    elif "portfolios" in base_output_name and "metrics" not in base_output_name:
        data_type = "portfolios"
    elif "portfolio_metrics" in base_output_name:
        data_type = "portfolio_metrics"

    # Open the Markdown file in the determined mode ('w' or 'a')
    try:
        # Write a header only if overwriting or file is new/empty
        if write_mode == 'w' or not os.path.exists(output_md_file) or os.path.getsize(output_md_file) == 0:
             with open(output_md_file, 'w', encoding='utf-8') as md_file_init:
                 md_file_init.write("# WealthArc Data Analysis Report\n")

        # Now open in append mode for the actual analysis
        with open(output_md_file, 'a', encoding='utf-8') as md_file:
            # Add section header including data type/endpoint source
            md_file.write(f"\n# Analysis for {data_type.capitalize()} Data (Source: {json_file})\n")

            df, csv_path = load_and_save_csv(json_file)

            if df is not None:
                analyze_data(df, data_type, base_output_name, md_file)
                logging.info(f"Analysis for {json_file} complete and appended to {output_md_file}.")
            else:
                logging.error(f"Failed to process {json_file}.")
                write_markdown(md_file, f"\n*Failed to load or process `{json_file}`.*\n")

    except Exception as e:
        logging.error(f"Failed to open or write to Markdown file {output_md_file}. Error: {e}", exc_info=True)
