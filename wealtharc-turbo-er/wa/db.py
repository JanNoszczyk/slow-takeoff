import duckdb
from loguru import logger
from wa import config
from pathlib import Path # Import Path

# Global connection object (can be managed more robustly if needed, e.g., context manager)
_con = None

# Define table names as constants for consistency
GOOGLE_TRENDS_TABLE = "google_trends_data"
WIKIMEDIA_CONTENT_TABLE = "wikimedia_content"
GDELT_MENTIONS_TABLE = "gdelt_mentions"
REDDIT_POSTS_TABLE = "reddit_posts"
STOCKTWITS_MESSAGES_TABLE = "stocktwits_messages"
SEC_FILINGS_TABLE = "sec_filings_metadata"
COMPANIES_HOUSE_COMPANIES_TABLE = "companies_house_companies"
COMPANIES_HOUSE_OFFICERS_TABLE = "companies_house_officers"
COMPANIES_HOUSE_FILINGS_TABLE = "companies_house_filings"
EPO_PATENTS_TABLE = "epo_patents"
USPTO_PATENTS_TABLE = "uspto_patents"
# Base tables used by ER or ingestors
ASSETS_TABLE = "assets"
ASSET_EMBEDDINGS_TABLE = "asset_embeddings"
# Raw Data Tables
RAW_FIGI_TABLE = "raw_figi"
RAW_FINNHUB_TABLE = "raw_finnhub"
RAW_IEX_TABLE = "raw_iex"
RAW_ALPHA_VANTAGE_TABLE = "raw_alpha_vantage"
RAW_FRED_TABLE = "raw_fred"
RAW_ECB_SDW_TABLE = "raw_ecb_sdw"
RAW_OPEN_EXCHANGE_RATES_TABLE = "raw_open_exchange_rates"
RAW_EIA_TABLE = "raw_eia"
RAW_QUANDL_LME_TABLE = "raw_quandl_lme"
RAW_COINGECKO_TABLE = "raw_coingecko"
RAW_WORLD_BANK_TABLE = "raw_world_bank"
RAW_IMF_TABLE = "raw_imf"
RAW_ESG_BOOK_TABLE = "raw_esg_book"
RAW_OFAC_SDN_TABLE = "raw_ofac_sdn"
RAW_GOOGLE_TRENDS_TABLE = "raw_google_trends"
RAW_WIKIMEDIA_TABLE = "raw_wikimedia" # Ensure this is present
RAW_NEWSAPI_TABLE = "raw_newsapi"
RAW_GDELT_TABLE = "raw_gdelt"
RAW_TWITTER_TABLE = "raw_twitter"
RAW_REDDIT_TABLE = "raw_reddit"
RAW_STOCKTWITS_TABLE = "raw_stocktwits"
RAW_SEC_EDGAR_TABLE = "raw_sec_edgar"
RAW_COMPANIES_HOUSE_TABLE = "raw_companies_house"
RAW_USPTO_TABLE = "raw_uspto"
RAW_EPO_TABLE = "raw_epo"
# Other Cleaned Tables
NEWS_RAW_TABLE = "news_raw" # Consider renaming or clarifying purpose vs raw_newsapi
TWEETS_TABLE = "tweets_raw" # Consider renaming or clarifying purpose vs raw_twitter

# ER Link Tables Constants
NEWS_ASSET_LINK_TABLE = "news_asset_link"
TWEET_ASSET_LINK_TABLE = "tweet_asset_link"
REDDIT_POST_ASSET_LINK_TABLE = "reddit_post_asset_link"
WIKIMEDIA_ASSET_LINK_TABLE = "wikimedia_asset_link"
STOCKTWITS_ASSET_LINK_TABLE = "stocktwits_asset_link"
SEC_FILING_ASSET_LINK_TABLE = "sec_filing_asset_link"
CH_FILING_ASSET_LINK_TABLE = "ch_filing_asset_link"
USPTO_PATENT_ASSET_LINK_TABLE = "uspto_patent_asset_link"
EPO_PATENT_ASSET_LINK_TABLE = "epo_patent_asset_link"
# Add more constants for other tables as needed

def get_db_connection(db_path: str | None = None):
    """
    Establishes and returns a new DuckDB database connection.
    Optionally accepts a path, otherwise uses the path from config.
    Installs and loads the VSS extension.
    NOTE: This function now ALWAYS returns a NEW connection. Management (closing) is caller's responsibility.
    """
    # global _con # Remove global connection management
    target_db_path_str = str(db_path or config.DB_PATH)
    target_db_path = Path(target_db_path_str)
    connection = None
    try:
        logger.info(f"Connecting to DuckDB database at: {target_db_path_str}")
        target_db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = duckdb.connect(database=target_db_path_str, read_only=False)

        # Install and load VSS extension on the new connection
        logger.info("Checking and installing DuckDB VSS extension if needed...")
        connection.sql("INSTALL vss;")
        connection.sql("LOAD vss;")
        logger.info("DuckDB VSS extension loaded successfully for this connection.")
        return connection

    except Exception as e:
        logger.error(f"Failed to connect to DuckDB or load VSS extension: {e}")
        if connection: # Attempt to close if partially opened
             connection.close()
        raise

def close_db_connection(con: duckdb.DuckDBPyConnection):
    """Closes the given database connection if it's open."""
    # global _con # Remove global connection management
    if con and not getattr(con, 'is_closed', lambda: True)(): # Use getattr for safety
        logger.info("Closing specific DuckDB connection.")
        con.close()

def create_schema(con: duckdb.DuckDBPyConnection):
    """
    Creates the necessary tables in the DuckDB database using the provided connection.
    """
    logger.info("Creating database schema if it doesn't exist...")
    try:
        # --- Raw Staging Tables ---
        # Use the full list including the newly added RAW_ table constants
        raw_tables = [
            RAW_FIGI_TABLE, RAW_FINNHUB_TABLE, RAW_IEX_TABLE, RAW_ALPHA_VANTAGE_TABLE, RAW_FRED_TABLE,
            RAW_ECB_SDW_TABLE, RAW_OPEN_EXCHANGE_RATES_TABLE, RAW_EIA_TABLE, RAW_QUANDL_LME_TABLE,
            RAW_COINGECKO_TABLE, RAW_WORLD_BANK_TABLE, RAW_IMF_TABLE, RAW_ESG_BOOK_TABLE,
            RAW_OFAC_SDN_TABLE, RAW_GOOGLE_TRENDS_TABLE, RAW_WIKIMEDIA_TABLE, RAW_NEWSAPI_TABLE,
            RAW_GDELT_TABLE, RAW_TWITTER_TABLE, RAW_REDDIT_TABLE, RAW_STOCKTWITS_TABLE,
            RAW_SEC_EDGAR_TABLE, RAW_COMPANIES_HOUSE_TABLE, RAW_USPTO_TABLE, RAW_EPO_TABLE
        ]
        for table_name in raw_tables:
            con.sql(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id VARCHAR PRIMARY KEY,
                    fetched_at TIMESTAMP WITH TIME ZONE,
                    payload JSON
                );
            """)
            logger.debug(f"Ensured table {table_name} exists.")

        # --- Clean Dimension / Fact Tables (Rest of schema as before) ---
        con.sql(f"""
            CREATE TABLE IF NOT EXISTS {ASSETS_TABLE} (
                asset_id VARCHAR PRIMARY KEY,
                name VARCHAR,
                ticker VARCHAR UNIQUE,
                asset_type VARCHAR,
                description TEXT,
                figi VARCHAR,
                last_updated TIMESTAMP WITH TIME ZONE
            );""")
        logger.debug(f"Ensured table {ASSETS_TABLE} exists.")
        con.sql("""
            CREATE TABLE IF NOT EXISTS quotes (
                quote_id VARCHAR PRIMARY KEY,
                asset_id VARCHAR REFERENCES assets(asset_id),
                timestamp TIMESTAMP WITH TIME ZONE,
                open DECIMAL,
                high DECIMAL,
                low DECIMAL,
                close DECIMAL,
                volume BIGINT,
                source VARCHAR
            );""")
        logger.debug("Ensured table quotes exists.")
        con.sql("""
            CREATE TABLE IF NOT EXISTS macro_series (
                series_id VARCHAR PRIMARY KEY,
                name VARCHAR,
                frequency VARCHAR,
                units VARCHAR,
                source VARCHAR,
                description TEXT,
                last_updated TIMESTAMP WITH TIME ZONE
            );""")
        logger.debug("Ensured table macro_series exists.")
        con.sql("""
            CREATE TABLE IF NOT EXISTS macro_data (
                data_id VARCHAR PRIMARY KEY,
                series_id VARCHAR REFERENCES macro_series(series_id),
                date DATE,
                value DECIMAL,
                fetched_at TIMESTAMP WITH TIME ZONE
            );""")
        logger.debug("Ensured table macro_data exists.")
        con.sql(f"""
            CREATE TABLE IF NOT EXISTS {NEWS_RAW_TABLE} (
                news_id VARCHAR PRIMARY KEY,
                asset_id VARCHAR,
                source_name VARCHAR,
                author VARCHAR,
                title TEXT,
                description TEXT,
                url VARCHAR UNIQUE,
                url_to_image VARCHAR,
                published_at TIMESTAMP WITH TIME ZONE,
                content TEXT,
                fetched_at TIMESTAMP WITH TIME ZONE
            );""")
        logger.debug(f"Ensured table {NEWS_RAW_TABLE} exists.")
        con.sql(f"""
            CREATE TABLE IF NOT EXISTS {TWEETS_TABLE} (
                tweet_id VARCHAR PRIMARY KEY,
                asset_id VARCHAR,
                user_id VARCHAR,
                username VARCHAR,
                text TEXT,
                created_at TIMESTAMP WITH TIME ZONE,
                public_metrics JSON,
                fetched_at TIMESTAMP WITH TIME ZONE
            );""")
        logger.debug(f"Ensured table {TWEETS_TABLE} exists.")
        con.sql("""
            CREATE TABLE IF NOT EXISTS sdn_entities (
                sdn_id VARCHAR PRIMARY KEY,
                name VARCHAR,
                entity_type VARCHAR,
                program VARCHAR,
                title VARCHAR,
                call_sign VARCHAR,
                vessel_type VARCHAR,
                tonnage VARCHAR,
                gross_registered_tonnage VARCHAR,
                vessel_flag VARCHAR,
                vessel_owner VARCHAR,
                remarks TEXT,
                raw_data JSON,
                fetched_at TIMESTAMP WITH TIME ZONE
            );""")
        logger.debug("Ensured table sdn_entities exists.")
        con.sql("""
             CREATE TABLE IF NOT EXISTS fx_rates (
                rate_id VARCHAR PRIMARY KEY,
                base_currency VARCHAR(3),
                target_currency VARCHAR(3),
                rate DECIMAL,
                timestamp TIMESTAMP WITH TIME ZONE,
                fetched_at TIMESTAMP WITH TIME ZONE
            );""")
        logger.debug("Ensured table fx_rates exists.")
        con.sql("""
            CREATE TABLE IF NOT EXISTS commodity_prices (
                price_id VARCHAR PRIMARY KEY,
                commodity_code VARCHAR,
                name VARCHAR,
                price DECIMAL,
                unit VARCHAR,
                date DATE,
                source VARCHAR,
                fetched_at TIMESTAMP WITH TIME ZONE
            );""")
        logger.debug("Ensured table commodity_prices exists.")
        con.sql("""
            CREATE TABLE IF NOT EXISTS esg_scores (
                esg_id VARCHAR PRIMARY KEY,
                asset_id VARCHAR REFERENCES assets(asset_id),
                isin VARCHAR,
                year INTEGER,
                overall_score DECIMAL,
                environment_score DECIMAL,
                social_score DECIMAL,
                governance_score DECIMAL,
                source VARCHAR DEFAULT 'ESG Book',
                fetched_at TIMESTAMP WITH TIME ZONE
            );""")
        logger.debug("Ensured table esg_scores exists.")
        con.sql(f"""
            CREATE TABLE IF NOT EXISTS {GOOGLE_TRENDS_TABLE} (
                trend_id VARCHAR PRIMARY KEY,
                keyword VARCHAR,
                asset_id VARCHAR REFERENCES assets(asset_id),
                date DATE,
                interest_score INTEGER,
                geo VARCHAR,
                source VARCHAR, -- Add the source column
                fetched_at TIMESTAMP WITH TIME ZONE
            );""")
        logger.debug(f"Ensured table {GOOGLE_TRENDS_TABLE} exists.")
        con.sql(f"""
            CREATE TABLE IF NOT EXISTS {WIKIMEDIA_CONTENT_TABLE} (
                page_id VARCHAR PRIMARY KEY,
                asset_id VARCHAR REFERENCES assets(asset_id),
                title VARCHAR,
                url VARCHAR UNIQUE,
                extract TEXT,
                full_content TEXT,
                last_revid BIGINT,
                modified_at TIMESTAMP WITH TIME ZONE,
                fetched_at TIMESTAMP WITH TIME ZONE
            );""")
        logger.debug(f"Ensured table {WIKIMEDIA_CONTENT_TABLE} exists.")
        con.sql(f"""
            CREATE TABLE IF NOT EXISTS {GDELT_MENTIONS_TABLE} (
                mention_id VARCHAR PRIMARY KEY,
                asset_id VARCHAR REFERENCES assets(asset_id),
                event_timestamp TIMESTAMP WITH TIME ZONE,
                mention_source_name VARCHAR,
                mention_type_name VARCHAR,
                mention_doc_tone DECIMAL,
                actor1_name VARCHAR,
                actor2_name VARCHAR,
                event_location_name VARCHAR,
                source_url VARCHAR,
                fetched_at TIMESTAMP WITH TIME ZONE
            );""")
        logger.debug(f"Ensured table {GDELT_MENTIONS_TABLE} exists.")
        con.sql(f"""
            CREATE TABLE IF NOT EXISTS {REDDIT_POSTS_TABLE} (
                post_id VARCHAR PRIMARY KEY,
                asset_id VARCHAR REFERENCES assets(asset_id),
                subreddit VARCHAR,
                title TEXT,
                selftext TEXT,
                author VARCHAR,
                created_utc TIMESTAMP WITH TIME ZONE,
                score INTEGER,
                num_comments INTEGER,
                url VARCHAR UNIQUE,
                fetched_at TIMESTAMP WITH TIME ZONE
            );""")
        logger.debug(f"Ensured table {REDDIT_POSTS_TABLE} exists.")
        con.sql(f"""
            CREATE TABLE IF NOT EXISTS {STOCKTWITS_MESSAGES_TABLE} (
                message_id BIGINT PRIMARY KEY,
                asset_id VARCHAR REFERENCES assets(asset_id),
                user_id BIGINT,
                username VARCHAR,
                body TEXT,
                created_at TIMESTAMP WITH TIME ZONE,
                sentiment VARCHAR,
                mentioned_symbols JSON,
                fetched_at TIMESTAMP WITH TIME ZONE
            );""")
        logger.debug(f"Ensured table {STOCKTWITS_MESSAGES_TABLE} exists.")
        con.sql(f"""
            CREATE TABLE IF NOT EXISTS {SEC_FILINGS_TABLE} (
                accession_number VARCHAR PRIMARY KEY,
                asset_id VARCHAR REFERENCES assets(asset_id),
                cik VARCHAR,
                company_name VARCHAR,
                form_type VARCHAR,
                filed_at DATE,
                period_of_report DATE,
                file_url VARCHAR,
                fetched_at TIMESTAMP WITH TIME ZONE
            );""")
        logger.debug(f"Ensured table {SEC_FILINGS_TABLE} exists.")
        con.sql(f"""
            CREATE TABLE IF NOT EXISTS {COMPANIES_HOUSE_COMPANIES_TABLE} (
                company_number VARCHAR PRIMARY KEY,
                asset_id VARCHAR REFERENCES assets(asset_id),
                company_name VARCHAR,
                company_status VARCHAR,
                company_type VARCHAR,
                jurisdiction VARCHAR,
                date_of_creation DATE,
                address JSON,
                sic_codes JSON,
                fetched_at TIMESTAMP WITH TIME ZONE
            );""")
        logger.debug(f"Ensured table {COMPANIES_HOUSE_COMPANIES_TABLE} exists.")
        con.sql(f"""
            CREATE TABLE IF NOT EXISTS {COMPANIES_HOUSE_OFFICERS_TABLE} (
                officer_id VARCHAR PRIMARY KEY,
                company_number VARCHAR REFERENCES companies_house_companies(company_number),
                name VARCHAR,
                role VARCHAR,
                nationality VARCHAR,
                appointed_on DATE,
                resigned_on DATE,
                address JSON,
                fetched_at TIMESTAMP WITH TIME ZONE
            );""")
        logger.debug(f"Ensured table {COMPANIES_HOUSE_OFFICERS_TABLE} exists.")
        con.sql(f"""
            CREATE TABLE IF NOT EXISTS {COMPANIES_HOUSE_FILINGS_TABLE} (
                transaction_id BIGINT PRIMARY KEY,
                company_number VARCHAR REFERENCES companies_house_companies(company_number),
                description VARCHAR,
                category VARCHAR,
                date DATE,
                barcode VARCHAR,
                links JSON,
                fetched_at TIMESTAMP WITH TIME ZONE
            );""")
        logger.debug(f"Ensured table {COMPANIES_HOUSE_FILINGS_TABLE} exists.")
        con.sql(f"""
            CREATE TABLE IF NOT EXISTS {EPO_PATENTS_TABLE} (
                publication_number VARCHAR PRIMARY KEY,
                asset_id VARCHAR REFERENCES assets(asset_id),
                title TEXT,
                abstract TEXT,
                applicant VARCHAR,
                inventor VARCHAR,
                publication_date DATE,
                priority_date DATE,
                ipc_classes JSON,
                cpc_classes JSON,
                family_id VARCHAR,
                fetched_at TIMESTAMP WITH TIME ZONE
            );""")
        logger.debug(f"Ensured table {EPO_PATENTS_TABLE} exists.")
        con.sql(f"""
            CREATE TABLE IF NOT EXISTS {USPTO_PATENTS_TABLE} (
                patent_number VARCHAR PRIMARY KEY,
                asset_id VARCHAR REFERENCES assets(asset_id),
                title TEXT,
                abstract TEXT,
                assignee VARCHAR,
                inventor VARCHAR,
                issue_date DATE,
                filing_date DATE,
                uspc_classes JSON,
                cpc_classes JSON,
                application_number VARCHAR,
                fetched_at TIMESTAMP WITH TIME ZONE
            );""")
        logger.debug(f"Ensured table {USPTO_PATENTS_TABLE} exists.")

        # --- ER Helper Tables ---
        con.sql(f"""
            CREATE TABLE IF NOT EXISTS {ASSET_EMBEDDINGS_TABLE} (
                embedding_id VARCHAR PRIMARY KEY,
                asset_id VARCHAR REFERENCES {ASSETS_TABLE}(asset_id),
                model_name VARCHAR,
                embedding FLOAT[], -- Assuming DuckDB supports array of floats for vectors
                text_source TEXT,
                generated_at TIMESTAMP WITH TIME ZONE
            );""")
        logger.debug(f"Ensured table {ASSET_EMBEDDINGS_TABLE} exists.")
        try:
            con.sql("SELECT vss_version();")
            con.sql(f"""CREATE INDEX IF NOT EXISTS asset_hnsw_idx ON {ASSET_EMBEDDINGS_TABLE} USING HNSW (embedding) WITH (metric = 'cosine');""")
            logger.info(f"Created HNSW index on {ASSET_EMBEDDINGS_TABLE}.embedding.")
        except Exception as e: logger.warning(f"Could not create HNSW index: {e}. VSS extension might not be loaded.")

        # --- ER Link Tables ---
        # Redefine create_link_table to use the more detailed schema
        def create_link_table(table_name: str, source_id_name: str, source_id_type: str, source_table: str | None = None):
             # Basic validation
             if not table_name or not source_id_name or not source_id_type:
                 logger.error(f"Missing required arguments for create_link_table for {table_name}")
                 return # Or raise an error

             # Construct foreign key constraint for source table if provided
             source_fk_constraint = ""
             if source_table:
                  source_fk_constraint = f"REFERENCES {source_table}({source_id_name})"

             con.sql(f"""
                 CREATE TABLE IF NOT EXISTS {table_name} (
                     link_id VARCHAR PRIMARY KEY, -- Consider UUID or composite key (asset_id, source_id)
                     {source_id_name} {source_id_type} {source_fk_constraint},
                     asset_id VARCHAR REFERENCES {ASSETS_TABLE}(asset_id),
                     relevance_score FLOAT,
                     link_method VARCHAR,
                     linked_at TIMESTAMP WITH TIME ZONE DEFAULT now() -- Use now() for DuckDB default timestamp
                 );""")
             logger.debug(f"Ensured table {table_name} exists.")
             # Add composite unique constraint?
             # con.sql(f"ALTER TABLE {table_name} ADD CONSTRAINT unique_{table_name}_link UNIQUE ({source_id_name}, asset_id);")

        create_link_table(NEWS_ASSET_LINK_TABLE, "news_id", "VARCHAR", source_table=NEWS_RAW_TABLE) # Assumes news_id is PK of news_raw
        create_link_table(TWEET_ASSET_LINK_TABLE, "tweet_id", "VARCHAR", source_table=TWEETS_TABLE) # Assumes tweet_id is PK of tweets_raw
        create_link_table(REDDIT_POST_ASSET_LINK_TABLE, "post_id", "VARCHAR", source_table=REDDIT_POSTS_TABLE)
        create_link_table(WIKIMEDIA_ASSET_LINK_TABLE, "page_id", "VARCHAR", source_table=WIKIMEDIA_CONTENT_TABLE)
        create_link_table(STOCKTWITS_ASSET_LINK_TABLE, "message_id", "BIGINT", source_table=STOCKTWITS_MESSAGES_TABLE)
        create_link_table(SEC_FILING_ASSET_LINK_TABLE, "accession_number", "VARCHAR", source_table=SEC_FILINGS_TABLE)
        create_link_table(CH_FILING_ASSET_LINK_TABLE, "transaction_id", "BIGINT", source_table=COMPANIES_HOUSE_FILINGS_TABLE) # Check ID type, assumed BIGINT
        create_link_table(USPTO_PATENT_ASSET_LINK_TABLE, "patent_number", "VARCHAR", source_table=USPTO_PATENTS_TABLE)
        create_link_table(EPO_PATENT_ASSET_LINK_TABLE, "publication_number", "VARCHAR", source_table=EPO_PATENTS_TABLE)

        logger.info("Database schema creation/verification complete.")

    except Exception as e:
        logger.error(f"Error during schema creation: {e}")
        raise

# Note: Removed the __main__ block for direct execution as connection management is now external
# If needed for testing, recreate it carefully managing connection creation/closing.

# IMPORTANT NOTE: The actual SQL definitions (...) were truncated for brevity in this example.
# The full, correct SQL from the previous version should be used here.
