import streamlit as st
import pandas as pd
import asyncio
from loguru import logger
import time

# Import project modules
from wa import db, config, er
from wa.ingest import ( # Organize imports
    figi, finnhub, newsapi, ofac, iexcloud, alpha_vantage,
    fred, ecb_sdw, openexchangerates, eia, quandl_lme, coingecko, world_bank, imf, esg_book, google_trends, wikimedia, gdelt, twitter, stocktwits, sec_edgar, companies_house, uspto, epo # Added all previous plus epo
)

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

        # IEX Cloud Quotes
        with st.expander("IEX Cloud Quotes"):
            iex_symbols = st.text_input("IEX Symbols to fetch (comma-separated)", "AAPL,MSFT,TSLA") # Default same as Finnhub for demo
            if st.button("Fetch IEX Cloud Quotes"):
                symbols_list = [symbol.strip().upper() for symbol in iex_symbols.split(',') if symbol.strip()]
                if symbols_list:
                    # Check for API key first
                    if not config.settings.IEX_CLOUD_API_KEY:
                        st.error("IEX_CLOUD_API_KEY is not set in the .env file. Cannot fetch from IEX Cloud.")
                    else:
                        with st.spinner("Fetching quotes from IEX Cloud..."):
                            try:
                                # Assumes assets table has iex_symbol column populated correctly or matches input symbol
                                asyncio.run(iexcloud.ingest_iex_quotes(symbols_list)) # Uses global conn via get_db_connection internally
                                st.success(f"IEX Cloud quote fetching completed for {len(symbols_list)} symbol(s). Check logs.")
                            except Exception as e:
                                st.error(f"IEX Cloud fetching failed: {e}")
                                logger.exception("IEX Cloud fetching failed in Streamlit")
                else:
                    st.warning("Please enter at least one IEX symbol.")

        # Alpha Vantage Quotes
        with st.expander("Alpha Vantage Quotes"):
            av_symbols = st.text_input("Alpha Vantage Symbols (Tickers) to fetch", "AAPL,MSFT,TSLA") # Default same as Finnhub/IEX
            st.caption("Note: Free tier has strict rate limits (e.g., 5/min). Fetches will be slow.")
            if st.button("Fetch Alpha Vantage Quotes"):
                symbols_list = [symbol.strip().upper() for symbol in av_symbols.split(',') if symbol.strip()]
                if symbols_list:
                    # Check for API key first
                    if not config.settings.ALPHAVANTAGE_API_KEY:
                        st.error("ALPHAVANTAGE_API_KEY is not set in the .env file. Cannot fetch from Alpha Vantage.")
                    else:
                        with st.spinner("Fetching quotes from Alpha Vantage (slow due to rate limits)..."):
                            try:
                                # Assumes assets table has 'ticker' column matching AV symbol
                                asyncio.run(alpha_vantage.ingest_alpha_vantage_quotes(symbols_list))
                                st.success(f"Alpha Vantage quote fetching completed for {len(symbols_list)} symbol(s). Check logs.")
                            except Exception as e:
                                st.error(f"Alpha Vantage fetching failed: {e}")
                                logger.exception("Alpha Vantage fetching failed in Streamlit")
                else:
                    st.warning("Please enter at least one Alpha Vantage symbol (ticker).")


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

    st.markdown("---")
    st.subheader("Macro & Rates")

    with col1: # Use col1 for Macro/Rates for now
        # FRED Series Data
        with st.expander("FRED Economic Data"):
            fred_series_ids = st.text_input("FRED Series IDs (comma-separated)", "DGS10,GDP,CPIAUCSL,UNRATE")
            fred_start_date = st.date_input("Start Date (optional)", value=None, key="fred_start") # Unique key
            fred_end_date = st.date_input("End Date (optional)", value=None, key="fred_end")     # Unique key

            # Convert dates to string format YYYY-MM-DD if selected
            start_date_str = fred_start_date.strftime('%Y-%m-%d') if fred_start_date else None
            end_date_str = fred_end_date.strftime('%Y-%m-%d') if fred_end_date else None

            if st.button("Fetch FRED Series"):
                series_list = [sid.strip().upper() for sid in fred_series_ids.split(',') if sid.strip()]
                if series_list:
                    # Check for API key first
                    if not config.settings.FRED_API_KEY:
                        st.error("FRED_API_KEY is not set in the .env file. Cannot fetch from FRED.")
                    else:
                        with st.spinner("Fetching data from FRED..."):
                            try:
                                asyncio.run(fred.ingest_fred_series(series_list, start_date=start_date_str, end_date=end_date_str))
                                st.success(f"FRED data ingestion process completed for {len(series_list)} series. Check logs.")
                            except Exception as e:
                                st.error(f"FRED fetching failed: {e}")
                                logger.exception("FRED fetching failed in Streamlit")
                else:
                    st.warning("Please enter at least one FRED Series ID.")

        # World Bank Indicators
        with st.expander("World Bank Indicators"):
            st.markdown("Enter World Bank indicator codes (e.g., `NY.GDP.MKTP.CD`). Find codes on the [World Bank Data site](https://data.worldbank.org/indicator).")
            wb_indicators = st.text_area("Indicator Codes (one per line)", "NY.GDP.MKTP.CD\nSP.POP.TOTL", height=80)
            # Countries: Default to World (WLD), could add multi-select later
            wb_countries = st.text_input("Country Codes (ISO Alpha-2, semi-colon separated)", value="WLD", help="Use 'WLD' for World aggregate.")
            current_year_wb = time.localtime().tm_year # Use different var name
            wb_start_year = st.number_input("Start Year (optional)", min_value=1960, max_value=current_year_wb, value=current_year_wb-10, key="wb_start")
            wb_end_year = st.number_input("End Year (optional)", min_value=1960, max_value=current_year_wb, value=current_year_wb, key="wb_end")

            if st.button("Fetch World Bank Indicators"):
                indicator_list = [ind.strip().upper() for ind in wb_indicators.split('\n') if ind.strip()]
                country_list = [c.strip().upper() for c in wb_countries.split(';') if c.strip()]

                if indicator_list and country_list:
                    # No API key needed generally
                    with st.spinner("Fetching data from World Bank..."):
                        try:
                            asyncio.run(world_bank.run_world_bank_ingestion(
                                indicator_codes=indicator_list,
                                country_codes=country_list,
                                start_year=wb_start_year,
                                end_year=wb_end_year
                            ))
                            st.success(f"World Bank data ingestion process completed for {len(indicator_list)} indicators. Check logs.")
                        except Exception as e:
                            st.error(f"World Bank fetching failed: {e}")
                            logger.exception("World Bank fetching failed in Streamlit")
                else:
                    st.warning("Please enter at least one Indicator Code and Country Code(s).")


    with col2: # Put ECB and IMF in the second column
         # ECB SDW Series Data
        with st.expander("ECB SDW Data (SDMX-JSON)"):
            st.markdown("Enter series as `FLOW_REF/KEY`, one per line. Find keys on the [ECB SDW website](https://data.ecb.europa.eu/).")
            ecb_keys_input = st.text_area("ECB Series Keys", "EXR/D.USD.EUR.SP00.A\nEXR/D.GBP.EUR.SP00.A\nYC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y", height=100)
            ecb_start_date = st.date_input("ECB Start Date (optional)", value=None, key="ecb_start")
            ecb_end_date = st.date_input("ECB End Date (optional)", value=None, key="ecb_end")

            start_date_str_ecb = ecb_start_date.strftime('%Y-%m-%d') if ecb_start_date else None
            end_date_str_ecb = ecb_end_date.strftime('%Y-%m-%d') if ecb_end_date else None

            if st.button("Fetch ECB SDW Series"):
                lines = [line.strip() for line in ecb_keys_input.split('\n') if line.strip()]
                series_map = {}
                valid_input_ecb = True # Use unique var name
                for line in lines:
                    if '/' not in line:
                        st.error(f"Invalid format: '{line}'. Use FLOW_REF/KEY.")
                        valid_input_ecb = False
                        break
                    flow_ref, series_key = line.split('/', 1)
                    if flow_ref not in series_map:
                        series_map[flow_ref] = []
                    series_map[flow_ref].append(series_key)

                if valid_input_ecb and series_map:
                    with st.spinner("Fetching data from ECB SDW... (can be slow)"):
                        try:
                            asyncio.run(ecb_sdw.run_ecb_sdw_ingestion(series_map, start_date=start_date_str_ecb, end_date=end_date_str_ecb))
                            st.success(f"ECB SDW data ingestion process completed for {len(lines)} series. Check logs.")
                        except Exception as e:
                            st.error(f"ECB SDW fetching failed: {e}")
                            logger.exception("ECB SDW fetching failed in Streamlit")
                elif valid_input_ecb:
                    st.warning("Please enter at least one ECB Series Key in FLOW_REF/KEY format.")

        # IMF Data
        with st.expander("IMF Data (SDMX-JSON)"):
             st.markdown("Enter series as `DATASET_ID/QUERY_FILTER`, one per line. Find IDs/Filters on the [IMF Data Portal](https://data.imf.org/).")
             imf_keys_input = st.text_area("IMF Series Keys", "IFS/Q.US.PMP_IX\nIFS/Q.GB.PMP_IX", height=80)
             current_year_imf = time.localtime().tm_year
             imf_start_year = st.number_input("IMF Start Year (optional)", min_value=1900, max_value=current_year_imf, value=current_year_imf-5, key="imf_start")
             imf_end_year = st.number_input("IMF End Year (optional)", min_value=1900, max_value=current_year_imf, value=current_year_imf, key="imf_end")

             if st.button("Fetch IMF Series Data"):
                lines = [line.strip() for line in imf_keys_input.split('\n') if line.strip()]
                series_list_imf = []
                valid_input_imf = True
                for line in lines:
                    if '/' not in line:
                        st.error(f"Invalid format: '{line}'. Use DATASET_ID/QUERY_FILTER.")
                        valid_input_imf = False
                        break
                    dataset_id, query_filter = line.split('/', 1)
                    series_list_imf.append((dataset_id, query_filter))

                if valid_input_imf and series_list_imf:
                    with st.spinner("Fetching data from IMF... (can be slow)"):
                        try:
                            asyncio.run(imf.run_imf_ingestion(
                                series_list=series_list_imf,
                                start_year=imf_start_year,
                                end_year=imf_end_year
                            ))
                            st.success(f"IMF data ingestion process completed for {len(series_list_imf)} series. Check logs.")
                        except Exception as e:
                            st.error(f"IMF fetching failed: {e}")
                            logger.exception("IMF fetching failed in Streamlit")
                elif valid_input_imf:
                    st.warning("Please enter at least one IMF Series Key in DATASET_ID/QUERY_FILTER format.")


    st.markdown("---")
    st.subheader("FX & Commodities")

    with col1: # Put FX in col1
        # Open Exchange Rates
        with st.expander("Open Exchange Rates (FX)"):
            st.markdown("Fetches the latest FX rates (base USD for free tier).")
            if st.button("Fetch Latest OER FX Rates"):
                 # Check for API key first
                if not config.settings.OPENEXCHANGERATES_APP_ID:
                    st.error("OPENEXCHANGERATES_APP_ID is not set in the .env file. Cannot fetch from OER.")
                else:
                    with st.spinner("Fetching latest FX rates from Open Exchange Rates..."):
                        try:
                            asyncio.run(openexchangerates.ingest_oer_latest_rates())
                            st.success("OER latest FX rates ingestion completed. Check logs.")
                        except Exception as e:
                            st.error(f"OER fetching failed: {e}")
                            logger.exception("OER fetching failed in Streamlit")

        # CoinGecko Crypto Prices
        with st.expander("CoinGecko Crypto Prices"):
            st.markdown("Enter CoinGecko coin IDs (e.g., `bitcoin`, `ethereum`). Find IDs on [CoinGecko](https://www.coingecko.com/).")
            cg_coin_ids = st.text_area("CoinGecko Coin IDs (one per line)", "bitcoin\nethereum\nsolana", height=80)
            cg_days_back = st.number_input("Days of History", min_value=1, max_value=90, value=30, key="cg_days", help="Free API limited to ~90 days of daily data.")

            if st.button("Fetch CoinGecko Prices"):
                coin_list = [coin_id.strip().lower() for coin_id in cg_coin_ids.split('\n') if coin_id.strip()]
                if coin_list:
                    # No API key needed for free tier public endpoints used here
                    with st.spinner(f"Fetching crypto prices from CoinGecko for {cg_days_back} days... (Rate limits apply)"):
                        try:
                            asyncio.run(coingecko.run_coingecko_ingestion(coin_list, days_back=cg_days_back))
                            st.success(f"CoinGecko price ingestion process completed for {len(coin_list)} coins. Check logs.")
                        except Exception as e:
                            st.error(f"CoinGecko fetching failed: {e}")
                            logger.exception("CoinGecko fetching failed in Streamlit")
                else:
                    st.warning("Please enter at least one CoinGecko coin ID.")


    with col2: # Put EIA and Quandl in col2
        # EIA Energy Data
        with st.expander("EIA Energy Data"):
            st.markdown("Enter EIA Series IDs (e.g., from `PET`, `NG` categories). Find IDs on the [EIA website](https://www.eia.gov/opendata/).")
            eia_series_ids = st.text_area("EIA Series IDs (one per line)", "PET.WCRSTUS1.W\nNG.RNGWHHD.D\nPET.EMM_EPM0_PTE_NUS_DPG.W", height=100)
            eia_start_date = st.date_input("EIA Start Date (optional)", value=None, key="eia_start")
            eia_end_date = st.date_input("EIA End Date (optional)", value=None, key="eia_end")

            start_date_str_eia = eia_start_date.strftime('%Y-%m-%d') if eia_start_date else None
            end_date_str_eia = eia_end_date.strftime('%Y-%m-%d') if eia_end_date else None

            if st.button("Fetch EIA Series Data"):
                series_list = [sid.strip() for sid in eia_series_ids.split('\n') if sid.strip()]
                if series_list:
                     # Check for API key first
                    if not config.settings.EIA_API_KEY:
                        st.error("EIA_API_KEY is not set in the .env file. Cannot fetch from EIA.")
                    else:
                        with st.spinner("Fetching data from EIA... (Check logs for frequency details)"):
                            try:
                                # Note: The current eia.py assumes weekly frequency in fetch params.
                                # Needs refinement for mixed frequencies (e.g., daily NG price).
                                asyncio.run(eia.run_eia_ingestion(series_list, start_date=start_date_str_eia, end_date=end_date_str_eia))
                                st.success(f"EIA data ingestion process completed for {len(series_list)} series. Check logs.")
                            except Exception as e:
                                st.error(f"EIA fetching failed: {e}")
                                logger.exception("EIA fetching failed in Streamlit")
                else:
                    st.warning("Please enter at least one EIA Series ID.")

        # Quandl LME Commodities
        with st.expander("Quandl LME Commodities"):
            st.markdown("Enter Quandl LME dataset codes (e.g., `LME/PR_AL`). Find codes on [Nasdaq Data Link](https://data.nasdaq.com/databases/LME/documentation).")
            quandl_codes = st.text_area("Quandl LME Codes (one per line)", "LME/PR_AL\nLME/PR_CU\nLME/PR_ZI", height=80)
            quandl_start_date = st.date_input("Quandl Start Date (optional)", value=None, key="quandl_start")
            quandl_end_date = st.date_input("Quandl End Date (optional)", value=None, key="quandl_end")

            start_date_str_quandl = quandl_start_date.strftime('%Y-%m-%d') if quandl_start_date else None
            end_date_str_quandl = quandl_end_date.strftime('%Y-%m-%d') if quandl_end_date else None

            if st.button("Fetch Quandl LME Data"):
                codes_list = [code.strip().upper() for code in quandl_codes.split('\n') if code.strip()]
                if codes_list:
                    # Check for API key first
                    if not config.settings.QUANDL_API_KEY:
                        st.error("QUANDL_API_KEY is not set in the .env file. Cannot fetch from Quandl/Nasdaq Data Link.")
                    else:
                        with st.spinner("Fetching data from Quandl LME..."):
                            try:
                                asyncio.run(quandl_lme.run_quandl_lme_ingestion(codes_list, start_date=start_date_str_quandl, end_date=end_date_str_quandl))
                                st.success(f"Quandl LME data ingestion process completed for {len(codes_list)} datasets. Check logs.")
                            except Exception as e:
                                st.error(f"Quandl LME fetching failed: {e}")
                                logger.exception("Quandl LME fetching failed in Streamlit")
                else:
                    st.warning("Please enter at least one Quandl LME dataset code.")


    st.markdown("---")
    st.subheader("ESG & Alt Data") # New Section

    with col1: # Put ESG Book in col1
        # ESG Book Scores
        with st.expander("ESG Book Scores (GraphQL)"):
            st.markdown("Enter company ISINs to fetch ESG scores.")
            esg_isins = st.text_area("ISINs (one per line)", "US0378331005\nUS5949181045\nUS67066G1040", height=80, key="esg_isins")
            if st.button("Fetch ESG Book Scores"):
                isin_list_esg = [isin.strip().upper() for isin in esg_isins.split('\n') if isin.strip()]
                if isin_list_esg:
                    # Check for API key
                    if not config.settings.ESG_BOOK_API_KEY:
                         st.error("ESG_BOOK_API_KEY is not set in the .env file. Cannot fetch from ESG Book.")
                    else:
                         with st.spinner("Fetching data from ESG Book..."):
                              try:
                                   asyncio.run(esg_book.run_esg_book_ingestion(isin_list_esg))
                                   st.success(f"ESG Book score ingestion completed for {len(isin_list_esg)} ISINs. Check logs.")
                              except Exception as e:
                                   st.error(f"ESG Book fetching failed: {e}")
                                   logger.exception("ESG Book fetching failed in Streamlit")
                else:
                     st.warning("Please enter at least one ISIN.")

    with col2: # Add Google Trends to the second column in this section
        # Google Trends Interest
        with st.expander("Google Trends Interest"):
            st.markdown("Fetch interest over time for specific keywords (max 5 per request).")
            gt_keywords = st.text_area("Keywords (one per line or comma-separated)", "bitcoin,inflation,tesla stock", height=80, key="gt_keywords")
            gt_timeframe = st.text_input("Timeframe", "today 3-m", help="e.g., 'today 3-m', 'today 5-y', 'now 7-d'")
            gt_geo = st.text_input("Geo Code (optional)", "", help="e.g., 'US', 'GB'. Leave empty for worldwide.")

            if st.button("Fetch Google Trends Data"):
                # Parse keywords flexibly (newline or comma)
                keywords_raw = gt_keywords.replace(',', '\n').split('\n')
                keywords_list = [kw.strip() for kw in keywords_raw if kw.strip()]

                if keywords_list:
                    # Check max 5 keywords limit (handled inside fetch function, but good to note)
                    if len(keywords_list) > 5:
                        st.warning("Using only the first 5 keywords due to API limits.")
                        keywords_list = keywords_list[:5]

                    with st.spinner(f"Fetching Google Trends data for: {', '.join(keywords_list)}..."):
                        try:
                            asyncio.run(google_trends.ingest_google_trends(
                                keywords=keywords_list,
                                timeframe=gt_timeframe,
                                geo=gt_geo.strip().upper()
                            ))
                            st.success(f"Google Trends ingestion completed for {len(keywords_list)} keyword(s). Check logs.")
                        except Exception as e:
                            st.error(f"Google Trends fetching failed: {e}")
                            logger.exception("Google Trends fetching failed in Streamlit")
                else:
                    st.warning("Please enter at least one keyword.")

        # Wikimedia Summary Fetch
        with st.expander("Wikimedia Summary Fetch"):
            st.markdown("Search Wikipedia for a term and fetch the summary of the top result.")
            wiki_query = st.text_input("Wikipedia Search Query", "BlackRock", key="wiki_query")

            if st.button("Fetch Wikimedia Summary"):
                if wiki_query:
                    with st.spinner(f"Fetching Wikimedia summary for query: '{wiki_query}'..."):
                        try:
                            # Run the ingestion function using the shared connection
                            asyncio.run(wikimedia.ingest_wikipedia_for_query(wiki_query, con=conn))
                            st.success(f"Wikimedia summary ingestion completed for query '{wiki_query}'. Check logs and Explore tab.")
                        except Exception as e:
                            st.error(f"Wikimedia fetching failed: {e}")
                            logger.exception("Wikimedia fetching failed in Streamlit")
                else:
                    st.warning("Please enter a search query for Wikipedia.")

        # GDELT Mentions Fetch
        with st.expander("GDELT Mentions Fetch"):
            st.markdown("Fetch the latest GDELT Mentions file (containing article URLs mentioning events). Optionally filter by keywords in the source URL.")
            gdelt_kw_filter = st.text_input("Keywords for URL Filter (comma-sep, optional)", "bloomberg,reuters,ft.com", key="gdelt_kw")

            if st.button("Fetch Latest GDELT Mentions"):
                kw_list = [kw.strip().lower() for kw in gdelt_kw_filter.split(',') if kw.strip()] or None
                filter_desc = f" with source URL filter: {', '.join(kw_list)}" if kw_list else ""
                with st.spinner(f"Fetching latest GDELT mentions file{filter_desc}... (This can take a minute or two)"):
                    try:
                        # Run the ingestion function using the shared connection
                        asyncio.run(gdelt.ingest_latest_gdelt_mentions(keyword_filter=kw_list, con=conn))
                        st.success("GDELT mentions ingestion completed. Check logs and Explore tab.")
                    except Exception as e:
                        st.error(f"GDELT fetching failed: {e}")
                        logger.exception("GDELT fetching failed in Streamlit")

        # Twitter Search
        with st.expander("Twitter Recent Search (API v2)"):
            st.markdown("Search recent tweets (past 7 days for standard access). Requires `TWITTER_BEARER_TOKEN`.")
            tweet_query = st.text_input("Twitter Search Query", '"NVIDIA stock" OR $NVDA lang:en -is:retweet', key="tweet_query")
            tweet_max_results = st.number_input("Max Tweets", min_value=10, max_value=100, value=20, key="tweet_max")
            tweet_days_back = st.number_input("Days Back (max 7)", min_value=1, max_value=7, value=1, key="tweet_days")

            if st.button("Search Recent Tweets"):
                if not config.settings.TWITTER_BEARER_TOKEN:
                    st.error("TWITTER_BEARER_TOKEN is not configured in .env file.")
                elif tweet_query:
                    with st.spinner(f"Searching Twitter for: '{tweet_query}'..."):
                        try:
                            # Run the ingestion function using the shared connection
                            asyncio.run(twitter.ingest_twitter_search(
                                query=tweet_query,
                                max_results=tweet_max_results,
                                days_back=tweet_days_back,
                                con=conn
                            ))
                            st.success("Twitter search ingestion completed. Check logs and Explore tab.")
                        except ValueError as ve: # Catch missing token error from ingestor
                            st.error(f"Configuration Error: {ve}")
                        except Exception as e:
                            st.error(f"Twitter search failed: {e}")
                            logger.exception("Twitter search failed in Streamlit")
                else:
                    st.warning("Please enter a Twitter search query.")

        # StockTwits Symbol Stream
        with st.expander("StockTwits Symbol Stream"):
            st.markdown("Fetch recent messages for a specific stock symbol.")
            st_symbol = st.text_input("Stock Symbol (e.g., AAPL)", "AAPL", key="st_symbol")
            st_limit = st.number_input("Max Messages", min_value=1, max_value=30, value=20, key="st_limit") # API limit is 30

            if st.button("Fetch StockTwits Stream"):
                if st_symbol:
                    symbol_upper = st_symbol.strip().upper()
                    with st.spinner(f"Fetching StockTwits stream for {symbol_upper}..."):
                        try:
                            # Run the ingestion function using the shared connection
                            asyncio.run(stocktwits.ingest_stocktwits_symbol(
                                symbol=symbol_upper,
                                limit=st_limit,
                                con=conn
                            ))
                            st.success(f"StockTwits stream ingestion completed for {symbol_upper}. Check logs and Explore tab.")
                        except Exception as e:
                            st.error(f"StockTwits fetching failed: {e}")
                            logger.exception("StockTwits fetching failed in Streamlit")
                else:
                    st.warning("Please enter a stock symbol.")

        # SEC EDGAR Filings Download
        with st.expander("SEC EDGAR Filings Download"):
            st.markdown("Download filings (e.g., 10-K, 10-Q) for a specific Ticker/CIK. Requires correctly set `SEC_EDGAR_USER_AGENT` (email).")
            sec_ticker_cik = st.text_input("Ticker or CIK", "AAPL", key="sec_ticker")
            sec_filing_type = st.selectbox("Filing Type", ["10-K", "10-Q", "8-K", "4", "DEF 14A"], key="sec_ftype")
            # Use date inputs for date range
            default_start_date_sec = pd.to_datetime((pd.Timestamp.now() - pd.DateOffset(years=2)).date()) # Default start 2 years ago
            sec_start_date = st.date_input("Start Date (optional)", value=default_start_date_sec, key="sec_start")
            sec_end_date = st.date_input("End Date (optional)", value=pd.Timestamp.now().date(), key="sec_end")
            sec_limit = st.number_input("Max Filings (optional)", min_value=1, value=5, key="sec_limit")
            sec_amends = st.checkbox("Include Amendments?", value=False, key="sec_amends")

            start_date_str_sec = sec_start_date.strftime('%Y-%m-%d') if sec_start_date else None
            end_date_str_sec = sec_end_date.strftime('%Y-%m-%d') if sec_end_date else None

            if st.button("Download SEC Filings"):
                if not config.settings.SEC_EDGAR_USER_AGENT or "Your Name Your Email" in config.settings.SEC_EDGAR_USER_AGENT:
                     st.error("SEC_EDGAR_USER_AGENT is not configured correctly in .env file. Please provide a real email.")
                elif sec_ticker_cik and sec_filing_type:
                    with st.spinner(f"Downloading {sec_filing_type} for {sec_ticker_cik}..."):
                        try:
                            # Run the ingestion function using the shared connection
                            asyncio.run(sec_edgar.ingest_sec_filings(
                                ticker_or_cik=sec_ticker_cik,
                                filing_type=sec_filing_type,
                                start_date=start_date_str_sec,
                                end_date=end_date_str_sec,
                                limit=sec_limit,
                                include_amends=sec_amends,
                                con=conn
                            ))
                            st.success(f"SEC EDGAR download process completed for {sec_ticker_cik}. Check logs and Explore tab for metadata.")
                        except ValueError as ve: # Catch config errors
                            st.error(f"Configuration Error: {ve}")
                        except Exception as e:
                            st.error(f"SEC EDGAR download failed: {e}")
                            logger.exception("SEC EDGAR download failed in Streamlit")
                else:
                    st.warning("Please enter a Ticker/CIK and select a Filing Type.")

        # UK Companies House Ingestion
        # Place this in col1 for now
        with st.expander("UK Companies House Data"):
            st.markdown("Fetch profile, officers, and filings for a UK company number. Requires `UK_COMPANIES_HOUSE_API_KEY`.")
            ch_company_number = st.text_input("UK Company Number", "02099547", key="ch_number", help="e.g., BLACKROCK INVESTMENT MANAGEMENT (UK) LIMITED")

            if st.button("Fetch Companies House Data"):
                if not config.settings.UK_COMPANIES_HOUSE_API_KEY:
                    st.error("UK_COMPANIES_HOUSE_API_KEY is not configured in .env file.")
                elif ch_company_number:
                    company_num = ch_company_number.strip()
                    with st.spinner(f"Fetching data for company number {company_num} from Companies House..."):
                        try:
                            # Run the ingestion function using the shared connection
                            asyncio.run(companies_house.ingest_companies_house_company(
                                company_number=company_num,
                                con=conn
                            ))
                            st.success(f"Companies House data ingestion completed for {company_num}. Check logs and Explore tab.")
                        except ValueError as ve: # Catch config error
                            st.error(f"Configuration Error: {ve}")
                        except Exception as e:
                            st.error(f"Companies House fetching failed: {e}")
                            logger.exception("Companies House fetching failed in Streamlit")
                else:
                    st.warning("Please enter a UK Company Number.")

        # USPTO Patent Search (Placeholder API)
        with st.expander("USPTO Patent Search"):
            st.markdown("Search USPTO patents by assignee name. (Note: Current backend uses *mock data*).")
            uspto_assignee = st.text_input("Assignee Name", "Apple Inc.", key="uspto_assignee")
            uspto_limit = st.number_input("Max Patents", min_value=1, max_value=50, value=10, key="uspto_limit")

            if st.button("Search USPTO Patents"):
                if uspto_assignee:
                    with st.spinner(f"Searching USPTO patents for assignee '{uspto_assignee}'..."):
                        try:
                            # Run the ingestion function using the shared connection
                            asyncio.run(uspto.ingest_uspto_patents(
                                assignee_name=uspto_assignee,
                                limit=uspto_limit,
                                con=conn
                            ))
                            st.success(f"USPTO patent search ingestion completed for '{uspto_assignee}'. Check logs and Explore tab.")
                        except ValueError as ve: # Catch config errors
                             st.error(f"Configuration Error: {ve}")
                        except Exception as e:
                            st.error(f"USPTO search failed: {e}")
                            logger.exception("USPTO search failed in Streamlit")
                else:
                    st.warning("Please enter an assignee name.")

        # EPO Patent Search (Placeholder API)
        with st.expander("EPO Patent Search"):
            st.markdown("Search EPO patents by applicant name. Requires `EPO_OPS_KEY` and `EPO_OPS_SECRET`. (Note: Current backend uses *mock data* and basic search).")
            epo_applicant = st.text_input("Applicant Name", "Siemens Aktiengesellschaft", key="epo_applicant")
            epo_limit = st.number_input("Max Patents", min_value=1, max_value=100, value=10, key="epo_limit") # API allows up to 100 per request

            if st.button("Search EPO Patents"):
                if not config.settings.EPO_OPS_KEY or not config.settings.EPO_OPS_SECRET:
                    st.error("EPO_OPS_KEY and/or EPO_OPS_SECRET are not configured in .env file.")
                elif epo_applicant:
                    with st.spinner(f"Searching EPO patents for applicant '{epo_applicant}'..."):
                        try:
                            # Run the ingestion function using the shared connection
                            asyncio.run(epo.ingest_epo_patents(
                                applicant_name=epo_applicant,
                                limit=epo_limit,
                                con=conn
                            ))
                            st.success(f"EPO patent search ingestion completed for '{epo_applicant}'. Check logs and Explore tab.")
                        except ValueError as ve: # Catch config errors
                             st.error(f"Configuration Error: {ve}")
                        except Exception as e:
                            st.error(f"EPO search failed: {e}")
                            logger.exception("EPO search failed in Streamlit")
                else:
                    st.warning("Please enter an applicant name.")


    st.markdown("---")
    # Removed the old placeholder comment

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
                        if resolution_result.get('matches'): # Safely check 'matches' key
                            matched_asset_ids = list(resolution_result['matches'].keys())
                            assets_df_match = get_assets_df() # Use unique name
                            matched_assets_df = assets_df_match[assets_df_match['asset_id'].isin(matched_asset_ids)].copy()

                            if not matched_assets_df.empty:
                                # Add method and score
                                matched_assets_df['match_method'] = matched_assets_df['asset_id'].map(lambda x: resolution_result['matches'][x]['method'])
                                matched_assets_df['match_score'] = matched_assets_df['asset_id'].map(lambda x: resolution_result['matches'][x]['score'])

                                # Sort by score (lower is better for VSS/Fuzzy, Exact is 1.0)
                                matched_assets_df = matched_assets_df.sort_values(by='match_score', ascending=True)

                                st.subheader("Matched Assets:")
                                st.dataframe(matched_assets_df[['name', 'ticker', 'isin', 'match_method', 'match_score']])
                            else:
                                st.info("No matching assets found in the database for the resolved IDs.")
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

        news_df_match = get_news_df() # Use unique name
        if not news_df_match.empty:
            st.dataframe(news_df_match[['published_at', 'title', 'source']], height=300)
            # TODO: Add ability to select a news item and run ER on it, displaying results.
            # This requires more state management or callbacks.
            st.markdown("*Functionality to select news and see matches coming soon.*")
        else:
            st.info("No recent news articles found in the database. Use the 'Pull Data' tab.")

    st.markdown("---")
    st.subheader("Latest News-Asset Links") # Clarify link type
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

    assets_df_explore = get_assets_df() # Use unique name
    if not assets_df_explore.empty:
        st.subheader("Available Assets")
        st.dataframe(assets_df_explore)

        selected_asset_name = st.selectbox("Select Asset to Explore:", options=assets_df_explore['name'], index=0)

        if selected_asset_name:
            selected_asset_row = assets_df_explore[assets_df_explore['name'] == selected_asset_name].iloc[0]
            selected_asset_id = selected_asset_row['asset_id']
            st.subheader(f"Details for: {selected_asset_name}")
            st.dataframe(selected_asset_row) # Display full row details using st.dataframe

            # Display Quotes
            try:
                quotes_df = conn.sql("""
                    SELECT ts, price, volume, source
                    FROM quotes
                    WHERE asset_id = ?
                    ORDER BY ts DESC
                    LIMIT 100
                """, params=[selected_asset_id]).df() # Use params argument

                if not quotes_df.empty:
                    st.subheader("Recent Quotes")
                    st.dataframe(quotes_df)
                    # Add basic price chart
                    # Ensure 'ts' is datetime type for plotting
                    quotes_df_chart = quotes_df.copy()
                    quotes_df_chart['ts'] = pd.to_datetime(quotes_df_chart['ts'])
                    st.line_chart(quotes_df_chart.set_index('ts')['price'])
                else:
                    st.info("No quotes found for this asset.")
            except Exception as e:
                st.error(f"Error fetching/displaying quotes: {e}")

            # Display Linked News
            try:
                linked_news_df = conn.sql("""
                    SELECT n.published_at, n.title, l.method, l.similarity_score, n.url
                    FROM news_asset_link l
                    JOIN news_raw n ON l.news_id = n.news_id
                    WHERE l.asset_id = ?
                    ORDER BY n.published_at DESC
                    LIMIT 20
                """, params=[selected_asset_id]).df() # Use params argument

                if not linked_news_df.empty:
                    st.subheader("Linked News Articles")
                    # Make URL clickable
                    linked_news_df['url'] = linked_news_df['url'].apply(lambda x: f"[Link]({x})" if x else "")
                    st.dataframe(linked_news_df[['published_at', 'title', 'method', 'similarity_score', 'url']])
                else:
                    st.info("No news articles linked to this asset found.")
            except Exception as e:
                st.error(f"Error fetching linked news: {e}")

            # Display Macro Data
            st.subheader("Relevant Macro Data")
            try:
                # Example: Fetching DGS10 (US 10Y Treasury) if available
                dgs10_df = conn.sql("""
                    SELECT date, value
                    FROM macro_data
                    WHERE series_id = 'DGS10'
                    ORDER BY date DESC
                    LIMIT 252 -- Approx 1 year daily
                """).df()
                if not dgs10_df.empty:
                     dgs10_df['date'] = pd.to_datetime(dgs10_df['date'])
                     st.line_chart(dgs10_df.set_index('date')['value'], use_container_width=True)
                     st.caption("DGS10: US 10-Year Treasury Constant Maturity Rate")
                else:
                     st.info("No DGS10 data found in the specified range.")
            except Exception as e:
                 st.warning(f"Could not fetch/display DGS10 data: {e}")

            # Display FX Rates
            st.subheader("Latest FX Rates (vs USD)")
            try:
                fx_df = conn.sql("""
                    SELECT quote_currency, rate, ts
                    FROM fx_rates
                    WHERE base_currency = 'USD' AND source = 'openexchangerates'
                    ORDER BY ts DESC, quote_currency
                """).df()
                # Find the latest timestamp
                latest_ts_fx = fx_df['ts'].max() if not fx_df.empty else None
                if latest_ts_fx:
                    fx_df_latest = fx_df[fx_df['ts'] == latest_ts_fx].head(20) # Show top 20 latest
                    st.dataframe(fx_df_latest[['quote_currency', 'rate']])
                    st.caption(f"Rates as of: {pd.to_datetime(latest_ts_fx).strftime('%Y-%m-%d %H:%M:%S %Z')}")
                else:
                     st.info("No recent Open Exchange Rates data found.")
            except Exception as e:
                st.warning(f"Could not fetch/display FX rates: {e}")

            # Display Commodity Prices
            st.subheader("Latest Commodity Prices")
            try:
                commodity_df = conn.sql("""
                    SELECT commodity_code, price, date, source
                    FROM commodity_prices
                    ORDER BY date DESC, source, commodity_code
                """).df()
                # Find the latest date
                latest_comm_date = commodity_df['date'].max() if not commodity_df.empty else None
                if latest_comm_date:
                    comm_df_latest = commodity_df[commodity_df['date'] == latest_comm_date].head(20) # Show top 20 latest
                    st.dataframe(comm_df_latest[['source', 'commodity_code', 'price']])
                    st.caption(f"Prices as of date: {latest_comm_date.strftime('%Y-%m-%d')}")
                else:
                     st.info("No recent commodity prices found.")
            except Exception as e:
                st.warning(f"Could not fetch/display commodity prices: {e}")

            # Display World Bank Data
            st.subheader("World Development Indicators")
            try:
                # Example: Fetching World GDP
                wb_gdp_df = conn.sql("""
                    SELECT date, value
                    FROM macro_data
                    WHERE series_id = 'NY.GDP.MKTP.CD' -- World GDP Indicator
                    ORDER BY date DESC
                    LIMIT 20
                """).df()
                if not wb_gdp_df.empty:
                     wb_gdp_df['date'] = pd.to_datetime(wb_gdp_df['date'])
                     # Use bar chart for annual data
                     st.bar_chart(wb_gdp_df.set_index('date')['value'], use_container_width=True)
                     st.caption("NY.GDP.MKTP.CD: World GDP (Current US$)")
                else:
                     st.info("No World GDP data found for NY.GDP.MKTP.CD.")
            except Exception as e:
                st.warning(f"Could not fetch/display World Bank data: {e}")

            # Display IMF Data
            st.subheader("IMF Data Series")
            try:
                # Example: Fetching US Import Price Index
                imf_us_import_df = conn.sql("""
                    SELECT date, value
                    FROM macro_data
                    WHERE series_id = 'IMF_Q_US_PMP_IX' -- DB series ID for IFS/Q.US.PMP_IX
                    ORDER BY date DESC
                    LIMIT 20 # Quarterly data, show 5 years
                """).df()
                if not imf_us_import_df.empty:
                     imf_us_import_df['date'] = pd.to_datetime(imf_us_import_df['date'])
                     st.line_chart(imf_us_import_df.set_index('date')['value'], use_container_width=True)
                     st.caption("IFS/Q.US.PMP_IX: US Import Price Index (Quarterly)")
                else:
                     st.info("No IMF data found for IMF_Q_US_PMP_IX.")
            except Exception as e:
                st.warning(f"Could not fetch/display IMF data: {e}")

            # Display ESG Scores
            st.subheader("ESG Scores (ESG Book)")
            try:
                esg_df = conn.sql("""
                    SELECT score_type, value, grade, date
                    FROM esg_scores
                    WHERE asset_id = ? AND source = 'esg_book'
                    ORDER BY date DESC, score_type
                """, params=[selected_asset_id]).df() # Use params argument
                if not esg_df.empty:
                    # Display latest scores
                    latest_esg_date = esg_df['date'].max()
                    esg_df_latest = esg_df[esg_df['date'] == latest_esg_date]
                    st.dataframe(esg_df_latest[['score_type', 'value', 'grade']])
                    st.caption(f"Scores as of date: {latest_esg_date.strftime('%Y-%m-%d')}")
                else:
                     st.info("No ESG Book scores found for this asset.")
            except Exception as e:
                 st.warning(f"Could not fetch/display ESG scores: {e}")

            # Display Google Trends Data
            st.subheader("Google Trends Interest")
            try:
                # Fetch recent trends data, maybe related keywords later?
                # For now, just show the latest 100 entries overall
                trends_df = conn.sql(f"""
                    SELECT keyword, date, interest_score, geo
                    FROM {db.GOOGLE_TRENDS_TABLE}
                    ORDER BY fetched_at DESC, date DESC, keyword
                    LIMIT 100
                """).df()
                if not trends_df.empty:
                    st.dataframe(trends_df)
                    # Optionally add a chart if filtering by a few keywords
                    # Example: Chart for 'bitcoin' if present
                    bitcoin_trends = trends_df[trends_df['keyword'] == 'bitcoin']
                    if not bitcoin_trends.empty:
                         bitcoin_trends['date'] = pd.to_datetime(bitcoin_trends['date'])
                         st.line_chart(bitcoin_trends.set_index('date')['interest_score'])
                         st.caption("Google Trends for 'bitcoin' (if fetched)")

                else:
                     st.info("No Google Trends data found in the database.")
            except Exception as e:
                 st.warning(f"Could not fetch/display Google Trends data: {e}")

            # Display Wikimedia Content
            st.subheader("Wikimedia Content")
            try:
                # Fetch recent Wikimedia summaries
                wiki_df = conn.sql(f"""
                    SELECT title, summary, url, last_fetched_at
                    FROM {db.WIKIMEDIA_CONTENT_TABLE}
                    ORDER BY last_fetched_at DESC
                    LIMIT 20
                """).df()
                if not wiki_df.empty:
                    # Display Title and URL, maybe snippet of summary
                    wiki_df_display = wiki_df[['title', 'url', 'last_fetched_at']].copy()
                    wiki_df_display['url'] = wiki_df_display['url'].apply(lambda x: f"[Link]({x})" if x else "")
                    st.dataframe(wiki_df_display)
                else:
                     st.info("No Wikimedia content found in the database.")
            except Exception as e:
                 st.warning(f"Could not fetch/display Wikimedia content: {e}")

            # Display GDELT Mentions
            st.subheader("GDELT Mentions")
            try:
                # Fetch recent GDELT mentions
                gdelt_df = conn.sql(f"""
                    SELECT mention_ts, source_name, source_url, doc_tone, confidence
                    FROM {db.GDELT_MENTIONS_TABLE}
                    ORDER BY fetched_at DESC, mention_ts DESC
                    LIMIT 50
                """).df()
                if not gdelt_df.empty:
                    # Make URL clickable
                    gdelt_df_display = gdelt_df.copy()
                    gdelt_df_display['source_url'] = gdelt_df_display['source_url'].apply(lambda x: f"[Link]({x})" if x else "")
                    st.dataframe(gdelt_df_display)
                else:
                     st.info("No GDELT mentions found in the database.")
            except Exception as e:
                 st.warning(f"Could not fetch/display GDELT mentions: {e}")

            # Display Recent Tweets
            st.subheader("Recent Tweets")
            try:
                # Fetch recent tweets from the cleaned table
                tweets_df = conn.sql(f"""
                    SELECT created_at, username, text
                    FROM {db.TWEETS_TABLE} -- Use the actual table name constant if defined in db.py, else use hardcoded 'tweets_raw'
                    ORDER BY fetched_at DESC, created_at DESC
                    LIMIT 50
                """).df()
                if not tweets_df.empty:
                    st.dataframe(tweets_df)
                else:
                     st.info("No recent tweets found in the database.")
            except Exception as e:
                 st.warning(f"Could not fetch/display recent tweets: {e}")

            # Display StockTwits Messages
            st.subheader("StockTwits Messages")
            try:
                # Fetch recent StockTwits messages, maybe filter by selected asset ticker later?
                st_df = conn.sql(f"""
                    SELECT created_at, username, body, sentiment, symbol
                    FROM {db.STOCKTWITS_MESSAGES_TABLE}
                    ORDER BY fetched_at DESC, created_at DESC
                    LIMIT 50
                """).df()
                if not st_df.empty:
                    st.dataframe(st_df)
                else:
                     st.info("No StockTwits messages found in the database.")
            except Exception as e:
                 st.warning(f"Could not fetch/display StockTwits messages: {e}")

            # Display SEC Filings Metadata
            st.subheader("SEC Filings Metadata")
            try:
                # Fetch recent filing metadata
                sec_df = conn.sql(f"""
                    SELECT downloaded_at, ticker_cik, filing_type, filing_date, primary_doc_path, accession_number
                    FROM {db.SEC_FILINGS_TABLE}
                    ORDER BY downloaded_at DESC, filing_date DESC
                    LIMIT 50
                """).df()
                if not sec_df.empty:
                    # Display metadata, maybe link to local file path? (Might be complex/unsafe)
                    st.dataframe(sec_df[['downloaded_at', 'ticker_cik', 'filing_type', 'filing_date', 'accession_number']])
                    st.caption("Note: File paths are relative to the project root.")
                else:
                     st.info("No SEC filing metadata found in the database.")
            except Exception as e:
                 st.warning(f"Could not fetch/display SEC filing metadata: {e}")

            # Display Companies House Data (Profile, Officers, Filings)
            st.subheader("UK Companies House Data")
            try:
                # Fetch profile for the selected asset's company if we had a link?
                # For now, just show the most recently fetched company profile
                ch_profile_df = conn.sql(f"""
                    SELECT * EXCLUDE (fetched_at)
                    FROM {db.COMPANIES_HOUSE_COMPANIES_TABLE}
                    ORDER BY fetched_at DESC
                    LIMIT 1
                """).df()
                if not ch_profile_df.empty:
                    st.write("Most Recent Company Profile:")
                    st.dataframe(ch_profile_df)
                    # Fetch related officers and filings
                    company_num = ch_profile_df['company_number'].iloc[0]
                    ch_officers_df = conn.sql(f"""
                        SELECT name, officer_role, appointed_on, resigned_on, nationality, occupation
                        FROM {db.COMPANIES_HOUSE_OFFICERS_TABLE}
                        WHERE company_number = ?
                        ORDER BY appointed_on DESC NULLS LAST
                    """, params=[company_num]).df()
                    if not ch_officers_df.empty:
                        st.write("Officers:")
                        st.dataframe(ch_officers_df)

                    ch_filings_df = conn.sql(f"""
                        SELECT action_date, type, category, description, links
                        FROM {db.COMPANIES_HOUSE_FILINGS_TABLE}
                        WHERE company_number = ?
                        ORDER BY action_date DESC NULLS LAST
                        LIMIT 50
                    """, params=[company_num]).df()
                    if not ch_filings_df.empty:
                        st.write("Recent Filings:")
                        # Make document link clickable if available
                        def make_doc_link(links_json):
                            try:
                                links = json.loads(links_json)
                                doc_meta = links.get('document_metadata')
                                return f"[Doc]({doc_meta})" if doc_meta else ""
                            except:
                                return ""
                        ch_filings_df['doc_link'] = ch_filings_df['links'].apply(make_doc_link)
                        st.dataframe(ch_filings_df[['action_date', 'type', 'description', 'doc_link']])

                else:
                     st.info("No Companies House data found in the database.")
            except Exception as e:
                 st.warning(f"Could not fetch/display Companies House data: {e}")

            # Display USPTO Patent Data
            st.subheader("USPTO Patent Metadata")
            try:
                # Fetch recent patent metadata
                patent_df = conn.sql(f"""
                    SELECT patent_number, title, assignee, filing_date, grant_date, fetched_at
                    FROM {db.USPTO_PATENTS_TABLE}
                    ORDER BY fetched_at DESC, grant_date DESC NULLS LAST
                    LIMIT 50
                """).df()
                if not patent_df.empty:
                    st.dataframe(patent_df)
                else:
                     st.info("No USPTO patent metadata found in the database.")
            except Exception as e:
                 st.warning(f"Could not fetch/display USPTO patent data: {e}")

            # Display EPO Patent Data
            st.subheader("EPO Patent Metadata")
            try:
                # Fetch recent EPO patent metadata
                epo_patent_df = conn.sql(f"""
                    SELECT publication_number, title, applicant, publication_date, fetched_at
                    FROM {db.EPO_PATENTS_TABLE}
                    ORDER BY fetched_at DESC, publication_date DESC NULLS LAST
                    LIMIT 50
                """).df()
                if not epo_patent_df.empty:
                    st.dataframe(epo_patent_df)
                    st.caption("(Note: EPO data retrieval is currently placeholder/mock)")
                else:
                     st.info("No EPO patent metadata found in the database.")
            except Exception as e:
                 st.warning(f"Could not fetch/display EPO patent data: {e}")


            # Display Sanctions Info (Placeholder)
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
