import duckdb
from loguru import logger
from wa import config

# Global connection object (can be managed more robustly if needed, e.g., context manager)
_con = None

def get_db_connection():
    """
    Establishes or returns the existing DuckDB database connection.
    Installs and loads the VSS extension.
    """
    global _con
    if _con is None or _con.is_closed():
        try:
            logger.info(f"Connecting to DuckDB database at: {config.DB_PATH}")
            # Ensure the parent directory exists
            config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            _con = duckdb.connect(database=str(config.DB_PATH), read_only=False)

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
        # Generic raw table structure - adapt 'payload' type if needed (e.g., BLOB for non-JSON)
        sources = [
            "figi", "finnhub", "iex", "alpha_vantage", "fred", "ecb_sdw", "open_exchange_rates",
            "eia", "quandl_lme", "coingecko", "world_bank", "imf", "esg_book", "ofac_sdn",
            "google_trends", "wikimedia", "newsapi", "gdelt", "twitter", "reddit", "stocktwits",
            "sec_edgar", "companies_house", "uspto", "epo"
        ]
        for source in sources:
            con.sql(f"""
                CREATE TABLE IF NOT EXISTS raw_{source} (
                    id VARCHAR PRIMARY KEY,              -- Unique ID for the raw record (e.g., URL, API ID)
                    fetched_at TIMESTAMP WITH TIME ZONE, -- Timestamp when data was fetched
                    payload JSON                         -- Raw payload as JSON (consider BLOB for non-JSON)
                );
            """)
            logger.debug(f"Ensured table raw_{source} exists.")

        # --- Clean Dimension / Fact Tables ---
        con.sql("""
            CREATE TABLE IF NOT EXISTS assets (
                asset_id INTEGER PRIMARY KEY,       -- Internal unique ID for the asset
                name VARCHAR,
                isin VARCHAR UNIQUE,
                cusip VARCHAR UNIQUE,
                wkn VARCHAR,
                ric VARCHAR UNIQUE,
                figi VARCHAR UNIQUE,
                ticker VARCHAR,
                currency VARCHAR(3),
                asset_class VARCHAR,             -- e.g., Equity, Bond, FX, Crypto, Commodity, Index
                country VARCHAR(2),              -- ISO 3166-1 alpha-2
                exchange VARCHAR,
                -- Add other relevant static attributes
                created_at TIMESTAMP WITH TIME ZONE DEFAULT current_timestamp,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT current_timestamp
                -- Consider adding UNIQUE constraints on combinations if needed
            );
        """)
        logger.debug("Ensured table assets exists.")

        con.sql("""
            CREATE TABLE IF NOT EXISTS quotes (
                asset_id INTEGER,
                ts TIMESTAMP WITH TIME ZONE,        -- Timestamp of the quote
                price DOUBLE,
                volume DOUBLE,                   -- Optional: Trading volume
                source VARCHAR,                  -- e.g., 'finnhub', 'iex', 'alpha_vantage'
                fetched_at TIMESTAMP WITH TIME ZONE,
                PRIMARY KEY (asset_id, ts, source) -- Composite key to allow multiple sources for same time
            );
        """)
        logger.debug("Ensured table quotes exists.")

        con.sql("""
            CREATE TABLE IF NOT EXISTS macro_series (
                series_id VARCHAR PRIMARY KEY,     -- e.g., 'DGS10' for FRED 10-Yr Treasury
                name VARCHAR,
                frequency VARCHAR,               -- e.g., 'Daily', 'Monthly', 'Annual'
                units VARCHAR,
                source VARCHAR                   -- e.g., 'fred', 'ecb_sdw', 'world_bank', 'imf'
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
                -- FOREIGN KEY (series_id) REFERENCES macro_series(series_id) -- Enable if needed
            );
        """)
        logger.debug("Ensured table macro_data exists.")

        con.sql("""
            CREATE TABLE IF NOT EXISTS news_raw (
                news_id VARCHAR PRIMARY KEY,         -- Unique ID (e.g., URL hash or API provided ID)
                source VARCHAR,                  -- e.g., 'newsapi', 'gdelt'
                published_at TIMESTAMP WITH TIME ZONE,
                fetched_at TIMESTAMP WITH TIME ZONE,
                title VARCHAR,
                url VARCHAR UNIQUE,
                snippet VARCHAR,                 -- Short description or abstract
                body TEXT,                       -- Full text if available
                sentiment_score DOUBLE,          -- Optional: Pre-computed sentiment
                sentiment_label VARCHAR          -- Optional: e.g., 'positive', 'negative', 'neutral'
                -- Add other metadata like author, publisher, language if available
            );
        """)
        logger.debug("Ensured table news_raw exists.")

        con.sql("""
            CREATE TABLE IF NOT EXISTS tweets_raw (
                tweet_id VARCHAR PRIMARY KEY,
                source VARCHAR DEFAULT 'twitter',
                created_at TIMESTAMP WITH TIME ZONE,
                fetched_at TIMESTAMP WITH TIME ZONE,
                user_id VARCHAR,
                username VARCHAR,
                text TEXT,
                -- Add other relevant tweet metadata (retweets, likes, geo, etc.)
                sentiment_score DOUBLE,
                sentiment_label VARCHAR
            );
        """)
        logger.debug("Ensured table tweets_raw exists.")

        con.sql("""
            CREATE TABLE IF NOT EXISTS sdn_entities (
                sdn_uid INTEGER PRIMARY KEY,           -- Unique ID from OFAC SDN list
                name VARCHAR NOT NULL,
                sdn_type VARCHAR,                    -- e.g., 'Individual', 'Entity', 'Vessel'
                program VARCHAR,                     -- Sanctions program(s)
                title VARCHAR,
                call_sign VARCHAR,
                vess_type VARCHAR,
                tonnage VARCHAR,
                grt VARCHAR,                         -- Gross Registered Tonnage
                vess_flag VARCHAR,
                vess_owner VARCHAR,
                remarks TEXT,
                raw_entry JSON,                      -- Store the original JSON entry
                fetched_at TIMESTAMP WITH TIME ZONE
            );
        """)
        logger.debug("Ensured table sdn_entities exists.")

        # --- ER Helper Tables ---
        con.sql(f"""
            CREATE TABLE IF NOT EXISTS asset_embeddings (
                asset_id INTEGER PRIMARY KEY,
                name VARCHAR,
                embedding FLOAT[{config.OPENAI_EMBEDDING_DIMENSIONS}], -- Using FLOAT array for VSS
                model_name VARCHAR DEFAULT '{config.OPENAI_EMBEDDING_MODEL}',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT current_timestamp,
                FOREIGN KEY (asset_id) REFERENCES assets(asset_id)
            );
        """)
        logger.debug("Ensured table asset_embeddings exists.")

        # Create HNSW index for faster vector search if VSS extension is loaded
        # Check if VSS is available before creating the index
        try:
            _con.sql("SELECT vss_version();")
            con.sql(f"""
                CREATE INDEX IF NOT EXISTS asset_hnsw_idx ON asset_embeddings
                USING HNSW (embedding) WITH (metric = 'cosine');
            """)
            logger.info("Created HNSW index on asset_embeddings.embedding.")
        except duckdb.CatalogException as e:
             logger.warning(f"Could not check VSS version or create HNSW index. VSS extension might not be fully loaded or functional: {e}")
        except Exception as e:
            logger.warning(f"Could not create HNSW index on asset_embeddings.embedding: {e}. VSS extension might not be loaded correctly.")


        con.sql("""
            CREATE TABLE IF NOT EXISTS news_asset_link (
                news_id VARCHAR,
                asset_id INTEGER,
                method VARCHAR,                  -- 'exact', 'fuzzy', 'vss'
                similarity_score DOUBLE,         -- Levenshtein distance, Jaro-Winkler score, cosine distance, etc.
                linked_at TIMESTAMP WITH TIME ZONE DEFAULT current_timestamp,
                PRIMARY KEY (news_id, asset_id, method)
                -- FOREIGN KEY (news_id) REFERENCES news_raw(news_id), -- Enable if needed
                -- FOREIGN KEY (asset_id) REFERENCES assets(asset_id)  -- Enable if needed
            );
        """)
        logger.debug("Ensured table news_asset_link exists.")

        # Add similar link tables for other sources (tweets, reddit, etc.) if needed

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
        close_db_connection()
