import streamlit as st
import pandas as pd
import asyncio
from loguru import logger
import time

# Import project modules
from wa import db, config, er
from wa.ingest import figi, finnhub, newsapi, ofac

# --- App Configuration ---
st.set_page_config(
    page_title="WealthArc Turbo ER",
    page_icon="🚀",
    layout="wide",
)

st.title("🚀 WealthArc Turbo Entity Resolution")
st.caption("Harvest public data, match entities, explore insights.")

# --- Database Connection ---
# Cache the connection using Streamlit's caching
@st.cache_resource
def get_cached_db_connection():
    logger.info("Initializing Streamlit DB connection...")
    try:
        # Ensure logs directory exists for config setup
        log_dir = config.PROJECT_ROOT / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        conn = db.get_db_connection()
        db.create_schema(conn) # Ensure schema exists on first run
        logger.info("Streamlit DB connection established and schema verified.")
        return conn
    except Exception as e:
        logger.error(f"Failed to establish Streamlit DB connection: {e}")
        st.error(f"Fatal Error: Could not connect to the database ({config.DB_PATH}). Please check logs. Error: {e}")
        st.stop() # Stop the app if DB connection fails

conn = get_cached_db_connection()

# --- Helper Functions ---
def get_assets_df():
    """Fetches assets from the database."""
    try:
        df = conn.sql("SELECT asset_id, name, isin, cusip, figi, ticker, asset_class, currency FROM assets ORDER BY name").df()
        return df
    except Exception as e:
        st.error(f"Error fetching assets: {e}")
        return pd.DataFrame()

def get_news_df(limit=50):
    """Fetches recent news articles from the database."""
    try:
        df = conn.sql(f"SELECT news_id, published_at, title, snippet, url, source FROM news_raw ORDER BY published_at DESC LIMIT {limit}").df()
        return df
    except Exception as e:
        st.error(f"Error fetching news: {e}")
        return pd.DataFrame()

# --- Tab Implementation ---
tab_pull, tab_match, tab_explore = st.tabs(["📥 Pull Data", "🔗 Match Entities", "📊 Explore"])

# === Pull Data Tab ===
with tab_pull:
    st.header("📥 Data Ingestion Control")
    st.markdown("Trigger data harvesting from various public APIs.")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Identifiers & Quotes")
        # FIGI Mapping
        with st.expander("OpenFIGI Mapping"):
            figi_isins = st.text_area("ISINs to map (one per line)", "US0378331005\nUS5949181045", height=100)
            if st.button("Run FIGI Mapping"):
                isins_list = [isin.strip() for isin in figi_isins.split('\n') if isin.strip()]
                if isins_list:
                    jobs = [{"idType": "ID_ISIN", "idValue": isin} for isin in isins_list]
                    with st.spinner("Mapping ISINs via OpenFIGI..."):
                        try:
                            asyncio.run(figi.ingest_figi_mappings(jobs, con=conn))
                            st.success(f"OpenFIGI mapping request completed for {len(jobs)} ISIN(s). Check logs for details.")
                            # Consider adding update_assets_with_figi call here or make it part of ingest
                        except Exception as e:
                            st.error(f"FIGI mapping failed: {e}")
                else:
                    st.warning("Please enter at least one ISIN.")

        # Finnhub Quotes
        with st.expander("Finnhub Quotes"):
            fh_tickers = st.text_input("Tickers to fetch (comma-separated)", "AAPL,MSFT,TSLA")
            if st.button("Fetch Finnhub Quotes"):
                tickers_list = [ticker.strip().upper() for ticker in fh_tickers.split(',') if ticker.strip()]
                if tickers_list:
                    with st.spinner("Fetching quotes from Finnhub..."):
                        try:
                            asyncio.run(finnhub.ingest_finnhub_quotes(tickers_list, con=conn))
                            st.success(f"Finnhub quote fetching completed for {len(tickers_list)} ticker(s). Check logs.")
                        except Exception as e:
                            st.error(f"Finnhub fetching failed: {e}")
                else:
                    st.warning("Please enter at least one ticker.")

    with col2:
        st.subheader("News & Sanctions")
        # NewsAPI Headlines
        with st.expander("NewsAPI Headlines"):
            news_query = st.text_input("News search query", "Apple OR Microsoft OR Tesla")
            news_max_articles = st.number_input("Max articles to fetch", min_value=10, max_value=100, value=20) # Limit for demo
            news_days_back = st.number_input("Days back to search", min_value=1, max_value=30, value=3) # Max 30 for free plan
            if st.button("Fetch News Headlines"):
                if news_query:
                    with st.spinner(f"Fetching news for '{news_query}'..."):
                        try:
                            asyncio.run(newsapi.ingest_newsapi_headlines(news_query, max_articles=news_max_articles, con=conn, days_back=news_days_back))
                            st.success(f"NewsAPI fetching completed for query '{news_query}'.")
                            # Refresh news display on match tab? Might need state management.
                        except Exception as e:
                            st.error(f"NewsAPI fetching failed: {e}")
                else:
                    st.warning("Please enter a news query.")

        # OFAC SDN List
        with st.expander("OFAC Sanctions List (SDN)"):
            st.markdown("Downloads and processes the latest Specially Designated Nationals list.")
            if st.button("Update OFAC SDN List"):
                with st.spinner("Downloading and processing OFAC SDN list..."):
                    try:
                        asyncio.run(ofac.ingest_ofac_sdn_list(con=conn))
                        st.success("OFAC SDN list processed successfully.")
                    except Exception as e:
                        st.error(f"OFAC SDN processing failed: {e}")

    # Placeholder for other ingestion triggers (add more expanders)
    st.markdown("---")
    st.markdown("*Add controls for other data sources (FRED, ECB, ESG Book, etc.) here.*")

# === Match Entities Tab ===
with tab_match:
    st.header("🔗 Entity Resolution")
    st.markdown("Manually trigger ER or view recent matches.")

    col_match1, col_match2 = st.columns([1, 2])

    with col_match1:
        st.subheader("Manual ER Trigger")
        er_text_content = st.text_area("Enter text to resolve:", "Apple reported strong iPhone sales.", height=150)
        er_text_title = st.text_input("Optional Title:", "Apple Sales News")
        er_text_id = st.text_input("Unique Text ID (optional):", f"manual_{int(time.time())}")

        if st.button("Resolve Text to Assets"):
            if er_text_content and er_text_id:
                with st.spinner(f"Running 3-stage ER for ID: {er_text_id}..."):
                    try:
                        # Ensure asset embeddings are computed before resolving
                        st.write("Ensuring asset embeddings are up-to-date...")
                        asyncio.run(er.compute_and_store_asset_embeddings(con=conn))
                        st.write("Running resolution pipeline...")
                        resolution_result = asyncio.run(er.resolve_text_to_assets(
                            text_id=er_text_id,
                            text_content=er_text_content,
                            text_title=er_text_title,
                            con=conn
                        ))
                        st.success("Resolution complete!")
                        st.json(resolution_result)

                        # Display matched assets
                        if resolution_result['matches']:
                            matched_asset_ids = list(resolution_result['matches'].keys())
                            assets_df = get_assets_df()
                            matched_assets_df = assets_df[assets_df['asset_id'].isin(matched_asset_ids)].copy()

                            # Add method and score
                            matched_assets_df['match_method'] = matched_assets_df['asset_id'].map(lambda x: resolution_result['matches'][x]['method'])
                            matched_assets_df['match_score'] = matched_assets_df['asset_id'].map(lambda x: resolution_result['matches'][x]['score'])

                            # Sort by score (lower is better for VSS/Fuzzy, Exact is 1.0)
                            # Simple sort assuming lower score is generally better
                            matched_assets_df = matched_assets_df.sort_values(by='match_score', ascending=True)

                            st.subheader("Matched Assets:")
                            st.dataframe(matched_assets_df[['name', 'ticker', 'isin', 'match_method', 'match_score']])
                        else:
                            st.info("No assets matched the provided text based on current thresholds.")

                    except ImportError as ie:
                         if 'async_lru' in str(ie):
                             st.error("Error: `async_lru` cache issue detected. Restarting the app might help. If running locally, ensure the package is installed.")
                             logger.error(f"ImportError suggesting async_lru issue: {ie}")
                         else:
                             st.error(f"ER failed due to import error: {ie}")
                    except Exception as e:
                        st.error(f"Entity Resolution failed: {e}")
                        logger.exception("ER pipeline failed in Streamlit app")
            else:
                st.warning("Please provide text content and a unique ID.")

    with col_match2:
        st.subheader("Recent News Articles for ER")
        st.markdown("Select a recent news article to see potential asset matches.")

        news_df = get_news_df()
        if not news_df.empty:
            st.dataframe(news_df[['published_at', 'title', 'source']], height=300)
            # TODO: Add ability to select a news item and run ER on it, displaying results.
            # This requires more state management or callbacks.
            st.markdown("*Functionality to select news and see matches coming soon.*")
        else:
            st.info("No recent news articles found in the database. Use the 'Pull Data' tab.")

    st.markdown("---")
    st.subheader("Latest ER Links")
    try:
        links_df = conn.sql("""
            SELECT l.news_id, a.name as asset_name, a.ticker, l.method, l.similarity_score, l.linked_at
            FROM news_asset_link l
            JOIN assets a ON l.asset_id = a.asset_id
            ORDER BY l.linked_at DESC
            LIMIT 20
        """).df()
        st.dataframe(links_df)
    except Exception as e:
        st.error(f"Error fetching latest ER links: {e}")


# === Explore Tab ===
with tab_explore:
    st.header("📊 Explore Asset Data")
    st.markdown("View assets, quotes, news links, and other metrics.")

    assets_df = get_assets_df()
    if not assets_df.empty:
        st.subheader("Available Assets")
        st.dataframe(assets_df)

        selected_asset = st.selectbox("Select Asset to Explore:", options=assets_df['name'], index=0)

        if selected_asset:
            selected_asset_id = assets_df[assets_df['name'] == selected_asset]['asset_id'].iloc[0]
            st.subheader(f"Details for: {selected_asset}")
            st.write(assets_df[assets_df['asset_id'] == selected_asset_id])

            # Display Quotes
            try:
                quotes_df = conn.sql("""
                    SELECT ts, price, volume, source
                    FROM quotes
                    WHERE asset_id = ?
                    ORDER BY ts DESC
                    LIMIT 100
                """, [selected_asset_id]).df()

                if not quotes_df.empty:
                    st.subheader("Recent Quotes")
                    st.dataframe(quotes_df)
                    # Add basic price chart
                    st.line_chart(quotes_df.set_index('ts')['price'])
                else:
                    st.info("No quotes found for this asset.")
            except Exception as e:
                st.error(f"Error fetching quotes: {e}")

            # Display Linked News
            try:
                linked_news_df = conn.sql("""
                    SELECT n.published_at, n.title, l.method, l.similarity_score, n.url
                    FROM news_asset_link l
                    JOIN news_raw n ON l.news_id = n.news_id
                    WHERE l.asset_id = ?
                    ORDER BY n.published_at DESC
                    LIMIT 20
                """, [selected_asset_id]).df()

                if not linked_news_df.empty:
                    st.subheader("Linked News Articles")
                    st.dataframe(linked_news_df)
                else:
                    st.info("No news articles linked to this asset found.")
            except Exception as e:
                st.error(f"Error fetching linked news: {e}")

            # Display Sanctions Info (Placeholder)
            # Check if asset name/aliases appear in sdn_entities
            st.subheader("Sanctions Check (Placeholder)")
            st.info("Functionality to check asset against OFAC SDN list coming soon.")
            # Example query idea:
            # SELECT * FROM sdn_entities WHERE name % 'Selected Asset Name' -- using fuzzy match

    else:
        st.warning("No assets found in the database. Use the 'Pull Data' tab to ingest data first.")

# --- Footer / Info ---
st.sidebar.markdown("---")
st.sidebar.info("WealthArc Turbo ER Demo")
st.sidebar.info(f"Database: `{config.DB_PATH.name}`")
# Add more info like last update times?
