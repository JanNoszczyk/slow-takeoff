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
USPTO_PATENTS_TABLE = "uspto_patents" # Added from previous step, verify existence
# Base tables used by ER or ingestors
ASSETS_TABLE = "assets"
ASSET_EMBEDDINGS_TABLE = "asset_embeddings"
RAW_TWITTER_TABLE = "raw_twitter"
RAW_STOCKTWITS_TABLE = "raw_stocktwits" # Add missing constant
NEWS_RAW_TABLE = "news_raw"
TWEETS_TABLE = "tweets_raw"

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
    Establishes or returns the existing DuckDB database connection.
    Optionally accepts a path, otherwise uses the path from config.
    Installs and loads the VSS extension.
    """
    global _con
    # Check only if _con is None, as is_closed() is not a standard duckdb attribute
    if _con is None:
        target_db_path_str = str(db_path or config.DB_PATH)
        target_db_path = Path(target_db_path_str)
        try:
            logger.info(f"Connecting to DuckDB database at: {target_db_path_str}")
            # Ensure the parent directory exists
            target_db_path.parent.mkdir(parents=True, exist_ok=True)
            _con = duckdb.connect(database=target_db_path_str, read_only=False)

            # Install and load VSS extension
            logger.info("Checking and installing DuckDB VSS extension if needed...")
            _con.sql("INSTALL vss;")
            _con.sql("LOAD vss;")
            logger.info("DuckDB VSS extension loaded successfully.")

        except Exception as e:
            logger.error(f"Failed to connect to DuckDB or load VSS extension: {e}")
            raise
    return _con

def close_db_connection():
    """Closes the database connection if it's open."""
    global _con
    if _con and not _con.is_closed():
        logger.info("Closing DuckDB connection.")
        _con.close()
        _con = None

def create_schema(con: duckdb.DuckDBPyConnection = None):
    """
    Creates the necessary tables in the DuckDB database if they don't exist.
    """
    if con is None:
        con = get_db_connection()

    logger.info("Creating database schema if it doesn't exist...")

    try:
        # --- Raw Staging Tables ---
        sources = [
            "figi", "finnhub", "iex", "alpha_vantage", "fred", "ecb_sdw", "open_exchange_rates",
            "eia", "quandl_lme", "coingecko", "world_bank", "imf", "esg_book", "ofac_sdn",
            "google_trends", "wikimedia", "newsapi", "gdelt", "twitter", "reddit", "stocktwits",
            "sec_edgar", "companies_house", "uspto", "epo"
        ]
        for source in sources:
            con.sql(f"""
                CREATE TABLE IF NOT EXISTS raw_{source} (
                    id VARCHAR PRIMARY KEY,
                    fetched_at TIMESTAMP WITH TIME ZONE,
                    payload JSON
                );
            """)
            logger.debug(f"Ensured table raw_{source} exists.")

        # --- Clean Dimension / Fact Tables ---
        con.sql(f"""
            CREATE TABLE IF NOT EXISTS {ASSETS_TABLE} (
                asset_id INTEGER PRIMARY KEY,
                name VARCHAR,
                isin VARCHAR UNIQUE,
                cusip VARCHAR UNIQUE,
                wkn VARCHAR,
                ric VARCHAR UNIQUE,
                figi VARCHAR UNIQUE,
                iex_symbol VARCHAR UNIQUE,
                ticker VARCHAR,
                currency VARCHAR(3),
                asset_class VARCHAR,
                country VARCHAR(2),
                exchange VARCHAR,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT current_timestamp,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT current_timestamp
            );
        """)
        logger.debug(f"Ensured table {ASSETS_TABLE} exists.")

        con.sql("""
            CREATE TABLE IF NOT EXISTS quotes (
                asset_id INTEGER,
                ts TIMESTAMP WITH TIME ZONE,
                price DOUBLE,
                volume DOUBLE,
                source VARCHAR,
                fetched_at TIMESTAMP WITH TIME ZONE,
                PRIMARY KEY (asset_id, ts, source)
            );
        """)
        logger.debug("Ensured table quotes exists.")

        con.sql("""
            CREATE TABLE IF NOT EXISTS macro_series (
                series_id VARCHAR PRIMARY KEY,
                name VARCHAR,
                frequency VARCHAR,
                units VARCHAR,
                source VARCHAR
            );
        """)
        logger.debug("Ensured table macro_series exists.")

        con.sql("""
            CREATE TABLE IF NOT EXISTS macro_data (
                series_id VARCHAR,
                date DATE,
                value DOUBLE,
                fetched_at TIMESTAMP WITH TIME ZONE,
                PRIMARY KEY (series_id, date)
            );
        """)
        logger.debug("Ensured table macro_data exists.")

        con.sql(f"""
            CREATE TABLE IF NOT EXISTS {NEWS_RAW_TABLE} (
                news_id VARCHAR PRIMARY KEY,
                source VARCHAR,
                published_at TIMESTAMP WITH TIME ZONE,
                fetched_at TIMESTAMP WITH TIME ZONE,
                title VARCHAR,
                url VARCHAR UNIQUE,
                snippet VARCHAR,
                body TEXT,
                sentiment_score DOUBLE,
                sentiment_label VARCHAR
            );
        """)
        logger.debug(f"Ensured table {NEWS_RAW_TABLE} exists.")

        con.sql(f"""
            CREATE TABLE IF NOT EXISTS {TWEETS_TABLE} (
                tweet_id VARCHAR PRIMARY KEY,
                source VARCHAR DEFAULT 'twitter',
                created_at TIMESTAMP WITH TIME ZONE,
                fetched_at TIMESTAMP WITH TIME ZONE,
                user_id VARCHAR,
                username VARCHAR,
                text TEXT,
                sentiment_score DOUBLE,
                sentiment_label VARCHAR
            );
        """)
        logger.debug(f"Ensured table {TWEETS_TABLE} exists.")

        con.sql("""
            CREATE TABLE IF NOT EXISTS sdn_entities (
                sdn_uid INTEGER PRIMARY KEY,
                name VARCHAR NOT NULL,
                sdn_type VARCHAR,
                program VARCHAR,
                title VARCHAR,
                call_sign VARCHAR,
                vess_type VARCHAR,
                tonnage VARCHAR,
                grt VARCHAR,
                vess_flag VARCHAR,
                vess_owner VARCHAR,
                remarks TEXT,
                raw_entry JSON,
                fetched_at TIMESTAMP WITH TIME ZONE
            );
        """)
        logger.debug("Ensured table sdn_entities exists.")

        con.sql("""
            CREATE TABLE IF NOT EXISTS fx_rates (
                base_currency VARCHAR(3),
                quote_currency VARCHAR(3),
                ts TIMESTAMP WITH TIME ZONE,
                rate DOUBLE,
                source VARCHAR,
                fetched_at TIMESTAMP WITH TIME ZONE DEFAULT current_timestamp,
                PRIMARY KEY (base_currency, quote_currency, ts, source)
            );
        """)
        logger.debug("Ensured table fx_rates exists.")

        con.sql("""
            CREATE TABLE IF NOT EXISTS commodity_prices (
                commodity_code VARCHAR,
                date DATE,
                price DOUBLE,
                source VARCHAR,
                units VARCHAR,
                fetched_at TIMESTAMP WITH TIME ZONE DEFAULT current_timestamp,
                PRIMARY KEY (commodity_code, date, source)
            );
        """)
        logger.debug("Ensured table commodity_prices exists.")

        con.sql("""
            CREATE TABLE IF NOT EXISTS esg_scores (
                asset_id INTEGER,
                score_type VARCHAR,
                value DOUBLE,
                grade VARCHAR,
                source VARCHAR DEFAULT 'esg_book',
                date DATE,
                fetched_at TIMESTAMP WITH TIME ZONE DEFAULT current_timestamp,
                PRIMARY KEY (asset_id, score_type, date, source)
            );
        """)
        logger.debug("Ensured table esg_scores exists.")

        con.sql(f"""
            CREATE TABLE IF NOT EXISTS {GOOGLE_TRENDS_TABLE} (
                keyword VARCHAR,
                date DATE,
                interest_score INTEGER,
                geo VARCHAR(2) DEFAULT 'WW',
                source VARCHAR DEFAULT 'google_trends',
                fetched_at TIMESTAMP WITH TIME ZONE DEFAULT current_timestamp,
                PRIMARY KEY (keyword, date, geo)
            );
        """)
        logger.debug(f"Ensured table {GOOGLE_TRENDS_TABLE} exists.")

        con.sql(f"""
            CREATE TABLE IF NOT EXISTS {WIKIMEDIA_CONTENT_TABLE} (
                page_id VARCHAR PRIMARY KEY,
                title VARCHAR,
                summary TEXT,
                url VARCHAR,
                last_fetched_at TIMESTAMP WITH TIME ZONE
            );
        """)
        logger.debug(f"Ensured table {WIKIMEDIA_CONTENT_TABLE} exists.")

        con.sql(f"""
            CREATE TABLE IF NOT EXISTS {GDELT_MENTIONS_TABLE} (
                global_event_id BIGINT,
                mention_ts TIMESTAMP WITH TIME ZONE,
                source_name VARCHAR,
                source_url VARCHAR,
                sentence_id INTEGER,
                doc_tone DOUBLE,
                confidence UINTEGER,
                fetched_at TIMESTAMP WITH TIME ZONE
            );
        """)
        logger.debug(f"Ensured table {GDELT_MENTIONS_TABLE} exists.")

        con.sql(f"""
            CREATE TABLE IF NOT EXISTS {REDDIT_POSTS_TABLE} (
                post_id VARCHAR PRIMARY KEY,
                subreddit VARCHAR,
                title VARCHAR,
                author VARCHAR,
                created_utc TIMESTAMP WITH TIME ZONE,
                fetched_at TIMESTAMP WITH TIME ZONE,
                score INTEGER,
                num_comments INTEGER,
                upvote_ratio DOUBLE,
                permalink VARCHAR,
                selftext TEXT
            );
        """)
        logger.debug(f"Ensured table {REDDIT_POSTS_TABLE} exists.")

        con.sql(f"""
            CREATE TABLE IF NOT EXISTS {STOCKTWITS_MESSAGES_TABLE} (
                message_id BIGINT PRIMARY KEY,
                symbol VARCHAR,
                user_id BIGINT,
                username VARCHAR,
                created_at TIMESTAMP WITH TIME ZONE,
                fetched_at TIMESTAMP WITH TIME ZONE,
                body TEXT,
                sentiment VARCHAR
            );
        """)
        logger.debug(f"Ensured table {STOCKTWITS_MESSAGES_TABLE} exists.")

        con.sql(f"""
            CREATE TABLE IF NOT EXISTS {SEC_FILINGS_TABLE} (
                accession_number VARCHAR PRIMARY KEY,
                ticker_cik VARCHAR,
                filing_type VARCHAR,
                filing_date DATE,
                primary_doc_path VARCHAR,
                downloaded_at TIMESTAMP WITH TIME ZONE
            );
        """)
        logger.debug(f"Ensured table {SEC_FILINGS_TABLE} exists.")

        con.sql(f"""
            CREATE TABLE IF NOT EXISTS {COMPANIES_HOUSE_COMPANIES_TABLE} (
                company_number VARCHAR PRIMARY KEY,
                company_name VARCHAR,
                company_status VARCHAR,
                company_type VARCHAR,
                date_of_creation DATE,
                registered_office_address JSON,
                sic_codes JSON,
                fetched_at TIMESTAMP WITH TIME ZONE
            );
        """)
        logger.debug(f"Ensured table {COMPANIES_HOUSE_COMPANIES_TABLE} exists.")

        con.sql(f"""
            CREATE TABLE IF NOT EXISTS {COMPANIES_HOUSE_OFFICERS_TABLE} (
                company_number VARCHAR,
                officer_id VARCHAR,
                name VARCHAR,
                officer_role VARCHAR,
                nationality VARCHAR,
                occupation VARCHAR,
                appointed_on DATE,
                resigned_on DATE,
                address JSON,
                fetched_at TIMESTAMP WITH TIME ZONE,
                PRIMARY KEY (company_number, officer_id)
            );
        """)
        logger.debug(f"Ensured table {COMPANIES_HOUSE_OFFICERS_TABLE} exists.")

        con.sql(f"""
            CREATE TABLE IF NOT EXISTS {COMPANIES_HOUSE_FILINGS_TABLE} (
                company_number VARCHAR,
                transaction_id BIGINT,
                category VARCHAR,
                type VARCHAR,
                action_date DATE,
                description VARCHAR,
                links JSON,
                fetched_at TIMESTAMP WITH TIME ZONE,
                PRIMARY KEY (company_number, transaction_id)
            );
        """)
        logger.debug(f"Ensured table {COMPANIES_HOUSE_FILINGS_TABLE} exists.")

        con.sql(f"""
            CREATE TABLE IF NOT EXISTS {EPO_PATENTS_TABLE} (
                publication_number VARCHAR PRIMARY KEY,
                title VARCHAR,
                applicant VARCHAR,
                publication_date DATE,
                fetched_at TIMESTAMP WITH TIME ZONE
            );
        """)
        logger.debug(f"Ensured table {EPO_PATENTS_TABLE} exists.")


        # --- ER Helper Tables ---
        con.sql(f"""
            CREATE TABLE IF NOT EXISTS {ASSET_EMBEDDINGS_TABLE} (
                asset_id INTEGER PRIMARY KEY,
                name VARCHAR,
                embedding FLOAT[{config.OPENAI_EMBEDDING_DIMENSIONS}],
                model_name VARCHAR DEFAULT '{config.OPENAI_EMBEDDING_MODEL}',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT current_timestamp,
                FOREIGN KEY (asset_id) REFERENCES {ASSETS_TABLE}(asset_id)
            );
        """)
        logger.debug(f"Ensured table {ASSET_EMBEDDINGS_TABLE} exists.")

        # Create HNSW index for faster vector search
        try:
            con.sql("SELECT vss_version();") # Check if VSS is loaded
            con.sql(f"""
                CREATE INDEX IF NOT EXISTS asset_hnsw_idx ON {ASSET_EMBEDDINGS_TABLE}
                USING HNSW (embedding) WITH (metric = 'cosine');
            """)
            logger.info(f"Created HNSW index on {ASSET_EMBEDDINGS_TABLE}.embedding.")
        except duckdb.CatalogException:
             logger.warning("VSS extension might not be fully loaded or functional. Could not create HNSW index.")
        except Exception as e:
            logger.warning(f"Could not create HNSW index on {ASSET_EMBEDDINGS_TABLE}.embedding: {e}. VSS extension might not be loaded correctly.")


        # --- ER Link Tables ---
        # News link table (already existed but ensure name consistency)
        con.sql(f"""
            CREATE TABLE IF NOT EXISTS {NEWS_ASSET_LINK_TABLE} (
                news_id VARCHAR,
                asset_id INTEGER,
                method VARCHAR,
                similarity_score DOUBLE,
                linked_at TIMESTAMP WITH TIME ZONE DEFAULT current_timestamp,
                PRIMARY KEY (news_id, asset_id, method)
                -- FOREIGN KEY (news_id) REFERENCES {NEWS_RAW_TABLE}(news_id),
                -- FOREIGN KEY (asset_id) REFERENCES {ASSETS_TABLE}(asset_id)
            );
        """)
        logger.debug(f"Ensured table {NEWS_ASSET_LINK_TABLE} exists.")

        # --- Generic Link Table Creation Function ---
        def create_link_table(table_name: str, source_id_name: str, source_id_type: str, source_table: str):
            # source_id_type should be 'VARCHAR' or 'BIGINT' etc. matching the source table's PK
            con.sql(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    {source_id_name} {source_id_type},
                    asset_id INTEGER,
                    method VARCHAR,
                    similarity_score DOUBLE,
                    linked_at TIMESTAMP WITH TIME ZONE DEFAULT current_timestamp,
                    PRIMARY KEY ({source_id_name}, asset_id, method)
                    -- Optional FOREIGN KEY constraints
                    -- FOREIGN KEY ({source_id_name}) REFERENCES {source_table}({source_id_name}),
                    -- FOREIGN KEY (asset_id) REFERENCES {ASSETS_TABLE}(asset_id)
                );
            """)
            logger.debug(f"Ensured table {table_name} exists.")

        # Create link tables for other sources using the helper
        create_link_table(TWEET_ASSET_LINK_TABLE, "tweet_id", "VARCHAR", TWEETS_TABLE)
        create_link_table(REDDIT_POST_ASSET_LINK_TABLE, "post_id", "VARCHAR", REDDIT_POSTS_TABLE)
        create_link_table(WIKIMEDIA_ASSET_LINK_TABLE, "page_id", "VARCHAR", WIKIMEDIA_CONTENT_TABLE)
        create_link_table(STOCKTWITS_ASSET_LINK_TABLE, "message_id", "BIGINT", STOCKTWITS_MESSAGES_TABLE)
        create_link_table(SEC_FILING_ASSET_LINK_TABLE, "accession_number", "VARCHAR", SEC_FILINGS_TABLE)
        # Ensure USPTO patents table is created (might be missing if not added before)
        con.sql(f"""
            CREATE TABLE IF NOT EXISTS {USPTO_PATENTS_TABLE} (
                patent_number VARCHAR PRIMARY KEY,
                title VARCHAR,
                assignee VARCHAR,
                filing_date DATE,
                grant_date DATE,
                fetched_at TIMESTAMP WITH TIME ZONE,
                abstract TEXT
            );
        """)
        logger.debug(f"Ensured table {USPTO_PATENTS_TABLE} exists.")

        create_link_table(CH_FILING_ASSET_LINK_TABLE, "transaction_id", "BIGINT", COMPANIES_HOUSE_FILINGS_TABLE)
        create_link_table(USPTO_PATENT_ASSET_LINK_TABLE, "patent_number", "VARCHAR", USPTO_PATENTS_TABLE)
        create_link_table(EPO_PATENT_ASSET_LINK_TABLE, "publication_number", "VARCHAR", EPO_PATENTS_TABLE)


        logger.info("Database schema creation/verification complete.")

    except Exception as e:
        logger.error(f"Error during schema creation: {e}")
        raise

if __name__ == "__main__":
    # Example usage: connect and create schema
    try:
        conn = get_db_connection()
        create_schema(conn)
        print(f"Database schema created/verified successfully in {config.DB_PATH}")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if _con: # Check if connection was successfully established before closing
            close_db_connection()
