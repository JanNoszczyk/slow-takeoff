import json
import nbformat

def create_demo_notebook_content():
    """Generates the content for demo.ipynb as a JSON string."""
    nb = nbformat.v4.new_notebook()

    # Correctly indented code strings for notebook cells
    imports_code = """
import asyncio
import pandas as pd
import duckdb
from loguru import logger
import matplotlib.pyplot as plt
import seaborn as sns
import sys
import os

# Add project root to path to allow importing 'wa' modules
# Adjust the path depth ('..', '..') if create_notebook.py is moved
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    print(f"Added project root to sys.path: {project_root}")

try:
    from wa import db, config, er
except ImportError as e:
    print(f"[ERROR] Failed to import 'wa' modules: {e}.")
    print("Make sure you run this notebook from a kernel started in the project root (`wealtharc-turbo-er`)")
    print(f"Current sys.path: {sys.path}")
    raise

# Configure plotting style
sns.set_theme(style="darkgrid")
logger.remove() # Remove default handler
logger.add(sys.stderr, level="INFO") # Log INFO and above to stderr in notebook
print("Imports successful, logger configured.")
"""

    connect_db_code = """
# Connect to the database (ensure bootstrap was run first)
conn = None # Initialize conn
try:
    conn = db.get_db_connection()
    logger.info(f"Connected to database: {config.DB_PATH}")
    # Verify schema exists (optional check)
    print("\\nTables in database:")
    conn.sql("SELECT table_name FROM information_schema.tables WHERE table_schema='main' ORDER BY table_name").show()
except Exception as e:
    logger.error(f"Failed to connect to DB: {e}")
    print(f"[ERROR] Failed to connect to DB: {e}")
    # conn remains None
"""

    fetch_news_code = """
# Fetch a recent news headline for ER demo
news_item = None # Initialize news_item
if conn:
    try:
        # Fetch one of the news articles added by bootstrap
        news_item_df = conn.sql("SELECT news_id, title, snippet, body, url FROM news_raw ORDER BY fetched_at DESC LIMIT 1").df()
        if not news_item_df.empty:
            news_item = news_item_df.iloc[0].to_dict()
            logger.info(f"Selected news item for ER: ID={news_item['news_id']}, Title='{news_item['title']}'")
            print(f"\\nHeadline selected for resolution: '{news_item['title']}'")
            print(f"Content Snippet: '{news_item.get('snippet', news_item.get('body', ''))[:200]}...'")
        else:
            logger.warning("No news items found in news_raw table. Run bootstrap or ingest news first.")
            print("\\n[WARN] No news items found in news_raw table. Run bootstrap script first.")
    except Exception as e:
        logger.error(f"Failed to fetch news item: {e}")
        print(f"[ERROR] Failed to fetch news item: {e}")
        # news_item remains None
else:
    logger.error("Database connection not available.")
    print("[ERROR] Database connection not available.")
"""

    run_er_code = """
# Run Entity Resolution on the selected news item
er_results = None # Initialize er_results
if conn and news_item:
    # Ensure embeddings are computed (might take time if first run after bootstrap)
    logger.info("Checking/computing asset embeddings (this may take a moment if not cached)...")
    print("\\nChecking/computing asset embeddings...")
    try:
        # Use asyncio.run() only if not already in an event loop (like in Jupyter)
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                 print("Asyncio loop already running, using await.")
                 # This part might need adjustment depending on Jupyter environment
                 # For simplicity, we might just stick to asyncio.run and accept potential nested loop errors in some environments
                 # await er.compute_and_store_asset_embeddings(con=conn) # If using await in notebook
                 asyncio.run(er.compute_and_store_asset_embeddings(con=conn)) # Default attempt
            else:
                 asyncio.run(er.compute_and_store_asset_embeddings(con=conn))
        except RuntimeError: # No running event loop
             asyncio.run(er.compute_and_store_asset_embeddings(con=conn))

        logger.info("Embeddings checked/computed.")
        print("Embeddings checked/computed.")
    except Exception as e:
        logger.error(f"Failed during embedding check/computation: {e}")
        print(f"[WARN] Failed during embedding check/computation: {e}. VSS might not work.")
        # Proceed anyway, VSS might just fail

    # Run the ER pipeline
    logger.info(f"Running ER for news_id: {news_item['news_id']}")
    print(f"Running ER pipeline for news ID: {news_item['news_id']}...")
    try:
        # Similar check for running loop for the main ER call
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                 # er_results = await er.resolve_text_to_assets(...) # If using await
                 er_results = asyncio.run(er.resolve_text_to_assets(
                     text_id=news_item['news_id'],
                     text_content=news_item.get('body', news_item.get('snippet', news_item['title'])),
                     text_title=news_item['title'],
                     con=conn))
            else:
                 er_results = asyncio.run(er.resolve_text_to_assets(
                     text_id=news_item['news_id'],
                     text_content=news_item.get('body', news_item.get('snippet', news_item['title'])),
                     text_title=news_item['title'],
                     con=conn))
        except RuntimeError: # No running event loop
            er_results = asyncio.run(er.resolve_text_to_assets(
                text_id=news_item['news_id'],
                text_content=news_item.get('body', news_item.get('snippet', news_item['title'])),
                text_title=news_item['title'],
                con=conn))

        logger.info("ER complete.")
        print("\\n--- Entity Resolution Results ---")
        print(json.dumps(er_results, indent=2)) # Pretty print JSON
    except Exception as e:
        logger.error(f"ER failed: {e}", exc_info=True)
        print(f"[ERROR] ER failed: {e}")
        # er_results remains None
else:
    logger.warning("Skipping ER run because DB connection or news item is missing.")
    print("\\n[WARN] Skipping ER run because DB connection or news item is missing.")
"""

    display_matches_code = """
# Display matched assets
assets_df = None # Initialize dataframe
if conn and er_results and er_results.get('matches'):
    matched_asset_ids = list(er_results['matches'].keys())
    logger.info(f"Found {len(matched_asset_ids)} matched asset(s): {matched_asset_ids}")
    if not matched_asset_ids:
        print("\\nNo assets matched.")
    else:
        try:
            # Need display import for Jupyter
            from IPython.display import display, HTML
            # Ensure asset_ids are integers for the query
            safe_asset_ids = [int(aid) for aid in matched_asset_ids]
            ids_tuple = tuple(safe_asset_ids)
            # Handle single ID case for IN operator correctly
            if len(ids_tuple) == 1:
                query = f"SELECT asset_id, name, ticker, isin FROM assets WHERE asset_id = {ids_tuple[0]}"
            else:
                query = f"SELECT asset_id, name, ticker, isin FROM assets WHERE asset_id IN {ids_tuple}"

            assets_df = conn.sql(query).df()

            if not assets_df.empty:
                # Add match method and score
                assets_df['match_method'] = assets_df['asset_id'].map(lambda x: er_results['matches'][x]['method'])
                assets_df['match_score'] = assets_df['asset_id'].map(lambda x: er_results['matches'][x]['score'])
                # Format score based on method for clarity
                assets_df['match_score'] = assets_df.apply(
                    lambda row: f"{row['match_score']:.0f}" if row['match_method'] == 'fuzzy' else f"{row['match_score']:.4f}",
                    axis=1
                )
                assets_df = assets_df.sort_values(by='match_score', ascending=True) # Lower score often better

                print("\\n--- Matched Assets ---")
                display(HTML(assets_df.to_html(index=False))) # Display as HTML table
            else:
                print("\\nMatched asset IDs found, but failed to retrieve asset details.")

        except Exception as e:
            logger.error(f"Failed to fetch or display matched assets: {e}", exc_info=True)
            print(f"[ERROR] Failed to fetch or display matched assets: {e}")

elif er_results:
    print("\\nNo assets matched.")
else:
    print("\\nER process did not run or failed.")

"""
    select_asset_plot_code = """
# Select one asset for plotting (e.g., Apple if matched, otherwise the first)
plot_asset_id = None
plot_asset_name = None
plot_asset_ticker = None
# Use assets_df if it was created in the previous cell
current_assets_df = assets_df if 'assets_df' in locals() and assets_df is not None else None

if conn and current_assets_df is not None and not current_assets_df.empty:
    # Try to find Apple (asset_id 1) first if it's in the matched df
    if 1 in current_assets_df['asset_id'].values:
        plot_asset_id = 1
    else:
        # Otherwise, pick the best match (first one in the sorted df)
        plot_asset_id = current_assets_df.iloc[0]['asset_id']

elif conn:
    # Fallback if ER didn't run or find matches: Use Apple (asset_id 1) if it exists
    try:
        check_apple = conn.sql("SELECT asset_id FROM assets WHERE asset_id = 1 LIMIT 1").fetchone()
        if check_apple:
            plot_asset_id = 1
            logger.warning("ER matches not available/used. Using default Asset ID 1 (Apple) for plotting.")
            print("\\n[WARN] ER matches not available/used. Using default Asset ID 1 (Apple) for plotting.")
        else:
            logger.warning("Default Asset ID 1 not found.")
            print("\\n[WARN] Default plotting Asset ID 1 (Apple) not found in DB.")
    except Exception as e:
        logger.error(f"Failed to check for default asset: {e}")
        print(f"[ERROR] Failed to check for default asset: {e}")


# Retrieve name and ticker for the selected plot_asset_id
if conn and plot_asset_id:
    try:
        asset_info = conn.sql("SELECT name, ticker FROM assets WHERE asset_id = ?", [int(plot_asset_id)]).fetchone()
        if asset_info:
            plot_asset_name, plot_asset_ticker = asset_info
            logger.info(f"Selected asset for plotting: ID={plot_asset_id}, Name='{plot_asset_name}', Ticker='{plot_asset_ticker}'")
            print(f"\\nSelected asset for plotting: {plot_asset_name} ({plot_asset_ticker})")
        else:
            logger.warning(f"Could not retrieve info for selected plot_asset_id: {plot_asset_id}")
            print(f"[WARN] Could not retrieve info for selected plot_asset_id: {plot_asset_id}")
            plot_asset_id = None # Reset if info not found
    except Exception as e:
        logger.error(f"Failed to get asset info for plotting: {e}")
        print(f"[ERROR] Failed to get asset info for plotting: {e}")
        plot_asset_id = None
else:
    logger.warning("Cannot select asset for plotting (DB connection issue or no asset selected).")
    print("\\n[WARN] Cannot select asset for plotting (DB connection issue or no asset selected).")

"""

    fetch_plot_data_code = """
# Fetch price quotes for the selected asset
quotes_df = pd.DataFrame()
if conn and plot_asset_id:
    try:
        quotes_df = conn.sql(\"\"\"
            SELECT ts, price
            FROM quotes
            WHERE asset_id = ? AND source = 'finnhub' -- Assuming finnhub quotes from bootstrap
            ORDER BY ts
        \"\"\", [int(plot_asset_id)]).df()
        logger.info(f"Fetched {len(quotes_df)} quotes for asset ID {plot_asset_id}.")
        if not quotes_df.empty:
            # Convert 'ts' to datetime if it's not already
            quotes_df['ts'] = pd.to_datetime(quotes_df['ts'])
            quotes_df = quotes_df.set_index('ts')
            print(f"\\nFound {len(quotes_df)} price points for {plot_asset_name}.")
            # Display latest few quotes
            from IPython.display import display, HTML
            print("Latest quotes:")
            display(HTML(quotes_df.tail().to_html()))
        else:
            print(f"No quotes found for {plot_asset_name} in the database.")
    except Exception as e:
        logger.error(f"Failed to fetch quotes for plotting: {e}")
        print(f"[ERROR] Failed to fetch quotes for plotting: {e}")
else:
    print("\\nCannot fetch quotes, asset ID not selected or DB connection issue.")

# --- Placeholder for Sentiment Data ---
# In a real scenario, you would fetch this from a source like GDELT or compute it.
# Here, we simulate some sentiment scores aligned with the quote timestamps.
sentiment_df = pd.DataFrame()
if not quotes_df.empty:
    # Simulate sentiment: random values for demo
    import numpy as np
    np.random.seed(42) # for reproducibility
    simulated_sentiment = np.random.uniform(-0.5, 0.5, size=len(quotes_df))
    sentiment_df = pd.DataFrame({
        'sentiment_score': simulated_sentiment
    }, index=quotes_df.index) # Use the same timestamp index
    logger.info("Generated simulated sentiment data for plotting.")
    print("\\nGenerated simulated sentiment data for demo plotting.")
else:
    logger.warning("No quote data available, cannot generate sentiment data.")
    print("\\n[WARN] No quote data available, cannot simulate sentiment data.")
"""

    plot_data_code = """
# Plot Price vs. (Simulated) Sentiment
if not quotes_df.empty and not sentiment_df.empty:
    fig, ax1 = plt.subplots(figsize=(12, 6))

    color = 'tab:blue'
    ax1.set_xlabel('Time')
    ax1.set_ylabel('Price (USD)', color=color)
    ax1.plot(quotes_df.index, quotes_df['price'], color=color, label=f'{plot_asset_ticker} Price', marker='.', linestyle='-')
    ax1.tick_params(axis='y', labelcolor=color)
    ax1.legend(loc='upper left')
    ax1.grid(True) # Add grid for price axis

    ax2 = ax1.twinx()  # instantiate a second axes that shares the same x-axis
    color = 'tab:red'
    ax2.set_ylabel('Simulated Sentiment Score', color=color)
    # Use a bar chart for sentiment to make it visually distinct
    ax2.bar(sentiment_df.index, sentiment_df['sentiment_score'], color=color, alpha=0.6, width=0.01, label='Sentiment') # Adjust width as needed
    # ax2.plot(sentiment_df.index, sentiment_df['sentiment_score'], color=color, linestyle='--', alpha=0.7, label='Sentiment')
    ax2.tick_params(axis='y', labelcolor=color)
    ax2.legend(loc='upper right')
    ax2.axhline(0, color='grey', lw=0.5) # Add horizontal line at zero sentiment
    ax2.grid(False) # Turn off grid for sentiment axis

    # Format x-axis dates
    import matplotlib.dates as mdates
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
    plt.gcf().autofmt_xdate() # Auto rotate date labels

    plt.title(f'{plot_asset_name} ({plot_asset_ticker}) - Price vs. Simulated Sentiment')
    plt.show()
    logger.info("Displayed plot.")

elif not quotes_df.empty:
    # Plot just the price if sentiment is missing
    fig, ax1 = plt.subplots(figsize=(12, 5))
    color = 'tab:blue'
    ax1.set_xlabel('Time')
    ax1.set_ylabel('Price (USD)', color=color)
    ax1.plot(quotes_df.index, quotes_df['price'], color=color, marker='.', linestyle='-')
    ax1.tick_params(axis='y', labelcolor=color)
    ax1.grid(True)
    import matplotlib.dates as mdates
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
    plt.gcf().autofmt_xdate()
    fig.tight_layout()
    plt.title(f'{plot_asset_name} ({plot_asset_ticker}) - Price')
    plt.show()
    logger.info("Displayed price-only plot.")
else:
    print("\\nNo data available to plot.")
    logger.warning("No data available for plotting.")

"""

    sanctions_check_code = """
# Check for Sanctions Flags (Placeholder Logic)
if conn and plot_asset_id and plot_asset_name:
    # Need display import for Jupyter if not already imported
    from IPython.display import display, HTML
    logger.info(f"Checking sanctions status for {plot_asset_name}...")
    print(f"\\nChecking sanctions status for {plot_asset_name}...")
    # Basic check: Does the asset name (or variations) appear in sdn_entities?
    # This is a very naive check and needs significant improvement for real use.
    # Consider checking aliases, fuzzy matching names, linking via identifiers if possible.
    try:
        # Using lower() + LIKE for basic check
        check_sql = \"\"\"
        SELECT sdn_uid, name, program
        FROM sdn_entities
        WHERE lower(name) LIKE lower(?) OR lower(name) LIKE lower(?)
        LIMIT 5;
        \"\"\"
        # Prepare search terms (e.g., just the company name part)
        simple_name = ""
        search_term1 = ""
        search_term2 = ""
        if plot_asset_name:
            # Extract likely company name part before common suffixes like Inc., Corp., PLC
            name_parts = plot_asset_name.split(',')
            core_name = name_parts[0].strip()
            # Further split and take first word if it looks like a multi-word name
            first_word = core_name.split(' ')[0]
            simple_name = first_word if len(core_name.split(' ')) > 1 else core_name

            search_term1 = f"%{core_name}%"
            search_term2 = f"%{simple_name}%"

        sanction_matches = conn.sql(check_sql, [search_term1, search_term2]).df()

        if not sanction_matches.empty:
            logger.warning(f"Potential Sanctions Match Found for '{plot_asset_name}':")
            print(f"\\n--- POTENTIAL SANCTIONS MATCH FOUND for {plot_asset_name} ---")
            display(HTML(sanction_matches.to_html(index=False)))
        else:
            logger.info(f"No direct name match found in SDN list for '{plot_asset_name}'.")
            print(f"\\nNo direct name match found in SDN list for '{plot_asset_name}'. (Note: This is a basic check).")

    except Exception as e:
        logger.error(f"Failed to perform sanctions check: {e}")
        print(f"\\n[ERROR] Failed to perform sanctions check: {e}")
else:
    print("\\nCould not perform sanctions check (DB connection or asset info missing).")
"""

    close_db_code = """
# Close the database connection
if 'conn' in locals() and conn:
    try:
        if not conn.is_closed():
             db.close_db_connection()
             logger.info("Database connection closed.")
             print("\\nDatabase connection closed.")
             conn = None # Reset variable
        else:
             logger.info("Database connection already closed.")
             print("\\nDatabase connection already closed.")
    except Exception as e:
        logger.error(f"Error closing DB connection: {e}")
        print(f"[ERROR] Error closing DB connection: {e}")
else:
    logger.info("Database connection variable 'conn' not found or is None.")
    print("\\nDatabase connection variable 'conn' not found or is None.")
"""

    # Assemble the notebook cells with markdown descriptions
    nb.cells.append(nbformat.v4.new_markdown_cell("# WealthArc Turbo ER - Demo Notebook"))
    nb.cells.append(nbformat.v4.new_markdown_cell("This notebook demonstrates the core functionalities:\n1. Connecting to the database.\n2. Fetching a recent news item.\n3. Running the 3-stage Entity Resolution pipeline.\n4. Displaying matched assets.\n5. Plotting price vs. (simulated) sentiment for a matched asset.\n6. Performing a basic sanctions check."))
    nb.cells.append(nbformat.v4.new_markdown_cell("## 1. Imports and Setup\nImports necessary libraries and sets up the Python path and logging."))
    nb.cells.append(nbformat.v4.new_code_cell(imports_code))
    nb.cells.append(nbformat.v4.new_markdown_cell("## 2. Connect to Database\nEstablishes a connection to the DuckDB database (`wa.db`) and ensures the schema exists."))
    nb.cells.append(nbformat.v4.new_code_cell(connect_db_code))
    nb.cells.append(nbformat.v4.new_markdown_cell("## 3. Fetch Sample News Headline\nRetrieves the most recently fetched news article from the `news_raw` table to use for the ER demonstration."))
    nb.cells.append(nbformat.v4.new_code_cell(fetch_news_code))
    nb.cells.append(nbformat.v4.new_markdown_cell("## 4. Run Entity Resolution\nRuns the 3-stage ER pipeline (Exact, Fuzzy, Vector Similarity Search) on the selected news headline. This involves potentially computing embeddings for assets if they haven't been generated yet."))
    nb.cells.append(nbformat.v4.new_code_cell(run_er_code))
    nb.cells.append(nbformat.v4.new_markdown_cell("## 5. Display Matched Assets\nShows the assets identified by the ER pipeline, along with the matching method and score."))
    nb.cells.append(nbformat.v4.new_code_cell(display_matches_code))
    nb.cells.append(nbformat.v4.new_markdown_cell("## 6. Select Asset and Fetch Data for Plotting\nSelects an asset (preferring Apple if matched, otherwise the best match or a default) and fetches its price quote data."))
    nb.cells.append(nbformat.v4.new_code_cell(select_asset_plot_code))
    nb.cells.append(nbformat.v4.new_code_cell(fetch_plot_data_code))
    nb.cells.append(nbformat.v4.new_markdown_cell("## 7. Plot Price vs. Sentiment\nGenerates a plot showing the selected asset's price trend against a *simulated* sentiment score (since real sentiment calculation/ingestion is not implemented in this basic demo)."))
    nb.cells.append(nbformat.v4.new_code_cell(plot_data_code))
    nb.cells.append(nbformat.v4.new_markdown_cell("## 8. Sanctions Check\nPerforms a *very basic* check to see if the selected asset's name appears in the OFAC SDN list."))
    nb.cells.append(nbformat.v4.new_code_cell(sanctions_check_code))
    nb.cells.append(nbformat.v4.new_markdown_cell("## 9. Close Connection\nCloses the connection to the DuckDB database."))
    nb.cells.append(nbformat.v4.new_code_cell(close_db_code))

    # Set notebook metadata (optional, helps identify kernel)
    nb.metadata.kernelspec = {
        "display_name": "Python 3 (ipykernel)",
        "language": "python",
        "name": "python3"
    }
    nb.metadata.language_info = {
        "name": "python",
        "version": "3.11" # Specify the target version
    }

    return nbformat.writes(nb)

if __name__ == "__main__":
    notebook_content = create_demo_notebook_content()
    # Print to stdout so the calling process can capture it
    print(notebook_content)
