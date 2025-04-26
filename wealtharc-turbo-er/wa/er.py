import duckdb
import time
from typing import List, Tuple, Optional, Dict, Any
from loguru import logger
import pandas as pd # Import pandas for date handling if needed in helper funcs
from tenacity import retry, stop_after_attempt, wait_exponential
from openai import OpenAI, APIError
from async_lru import alru_cache

from wa import db, config
from wa.db import ( # Import specific table names needed for mapping
    ASSETS_TABLE, ASSET_EMBEDDINGS_TABLE, # Base tables
    NEWS_RAW_TABLE, TWEETS_TABLE, REDDIT_POSTS_TABLE, WIKIMEDIA_CONTENT_TABLE,
    STOCKTWITS_MESSAGES_TABLE, SEC_FILINGS_TABLE, COMPANIES_HOUSE_FILINGS_TABLE,
    USPTO_PATENTS_TABLE, EPO_PATENTS_TABLE,
    # Link tables
    NEWS_ASSET_LINK_TABLE, TWEET_ASSET_LINK_TABLE, REDDIT_POST_ASSET_LINK_TABLE,
    WIKIMEDIA_ASSET_LINK_TABLE, STOCKTWITS_ASSET_LINK_TABLE, SEC_FILING_ASSET_LINK_TABLE,
    CH_FILING_ASSET_LINK_TABLE, USPTO_PATENT_ASSET_LINK_TABLE, EPO_PATENT_ASSET_LINK_TABLE
)


# Initialize OpenAI client
if config.OPENAI_API_KEY:
    openai_client = OpenAI(api_key=config.OPENAI_API_KEY)
else:
    logger.warning("OPENAI_API_KEY not found. Vector Similarity Search (VSS) will not function.")
    openai_client = None

# --- Embedding Generation ---

@alru_cache(maxsize=1024)
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def get_openai_embedding(text: str, model: str = config.OPENAI_EMBEDDING_MODEL, dimensions: Optional[int] = config.OPENAI_EMBEDDING_DIMENSIONS) -> Optional[List[float]]:
    """Generates an embedding for the given text using OpenAI API with retries."""
    if not openai_client:
        logger.error("OpenAI client not initialized. Cannot generate embeddings.")
        return None
    if not text or not isinstance(text, str):
        logger.warning(f"Invalid input text for embedding: {text}")
        return None

    text = text.replace("\n", " ").strip()
    if not text:
        logger.warning("Empty text after cleaning, cannot generate embedding.")
        return None

    try:
        logger.debug(f"Requesting OpenAI embedding for text (len={len(text)}): '{text[:100]}...'")
        params = {"input": [text], "model": model}
        if dimensions:
            params["dimensions"] = dimensions

        # Note: OpenAI client's async methods might need specific handling in some event loops.
        # Ensure compatibility with how this function is called (e.g., via asyncio.run or existing loop).
        response = await openai_client.embeddings.create(**params)
        embedding = response.data[0].embedding
        logger.debug(f"Received embedding of dimension {len(embedding)}")
        return embedding
    except APIError as e:
        logger.error(f"OpenAI API error during embedding generation: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during embedding generation: {e}")
        raise


async def compute_and_store_asset_embeddings(asset_ids: Optional[List[int]] = None, con: Optional[duckdb.DuckDBPyConnection] = None):
    """Computes and stores OpenAI embeddings for assets missing them."""
    if not openai_client:
        logger.error("OpenAI client not initialized. Cannot compute asset embeddings.")
        return

    close_conn_locally = False
    if con is None:
        con = db.get_db_connection()
        close_conn_locally = True

    try:
        logger.info("Computing and storing missing asset embeddings...")
        base_query = f"""
            SELECT a.asset_id, a.name
            FROM {db.ASSETS_TABLE} a
            LEFT JOIN {db.ASSET_EMBEDDINGS_TABLE} ae ON a.asset_id = ae.asset_id
            WHERE ae.asset_id IS NULL AND a.name IS NOT NULL AND TRIM(a.name) != ''
        """
        if asset_ids:
            asset_id_list_str = ", ".join(map(str, asset_ids))
            query = f"{base_query} AND a.asset_id IN ({asset_id_list_str});"
        else:
            query = f"{base_query};"

        assets_to_embed = con.sql(query).fetchall()
        logger.info(f"Found {len(assets_to_embed)} assets requiring embeddings.")
        if not assets_to_embed: return

        insert_sql = f"""
            INSERT INTO {db.ASSET_EMBEDDINGS_TABLE} (asset_id, name, embedding, model_name)
            VALUES (?, ?, ?, '{config.OPENAI_EMBEDDING_MODEL}')
            ON CONFLICT (asset_id) DO UPDATE SET
                name = excluded.name,
                embedding = excluded.embedding,
                model_name = excluded.model_name,
                created_at = current_timestamp;
        """
        embeddings_added = 0
        for asset_id, name in assets_to_embed:
            try:
                embedding = await get_openai_embedding(name)
                if embedding:
                    con.execute(insert_sql, [asset_id, name, embedding])
                    embeddings_added += 1
                    logger.debug(f"Stored embedding for asset_id={asset_id}, name='{name}'")
                else:
                    logger.warning(f"Could not generate embedding for asset_id={asset_id}, name='{name}'")
            except Exception as e:
                logger.error(f"Failed to process embedding for asset_id={asset_id}, name='{name}': {e}")

        logger.info(f"Successfully computed and stored {embeddings_added} new asset embeddings.")
    except Exception as e:
        logger.error(f"Error during asset embedding computation: {e}")
    finally:
        if close_conn_locally and con:
            db.close_db_connection()

# --- Entity Resolution Stages (Modified to accept generic source_id) ---

def resolve_exact(source_id: str, text_content: str, con: duckdb.DuckDBPyConnection) -> List[Tuple[str, int, float]]:
    """Stage 1: Match text content against asset identifiers."""
    matches = []
    if not text_content or not isinstance(text_content, str): return matches
    logger.debug(f"Running exact match for source_id={source_id}")
    potential_ids = list(set(word for word in text_content.split() if 3 < len(word) < 20 and any(c.isalnum() for c in word)))
    if not potential_ids: return matches
    placeholders = ', '.join(['?'] * len(potential_ids))
    sql = f"""
        SELECT asset_id FROM {db.ASSETS_TABLE}
        WHERE isin IN ({placeholders}) OR cusip IN ({placeholders}) OR figi IN ({placeholders})
           OR ticker IN ({placeholders}) OR ric IN ({placeholders}) OR wkn IN ({placeholders});
    """
    params = potential_ids * 6
    try:
        for (asset_id,) in con.sql(sql, params).fetchall():
            matches.append((source_id, asset_id, 1.0))
            logger.info(f"Exact match found: source_id={source_id} -> asset_id={asset_id}")
    except Exception as e: logger.error(f"Error during exact match query for source_id={source_id}: {e}")
    return matches

def resolve_fuzzy(source_id: str, text_title: str, con: duckdb.DuckDBPyConnection, threshold: int = 4) -> List[Tuple[str, int, float]]:
    """Stage 2: Fuzzy string matching between text title and asset names."""
    matches = []
    if not text_title or not isinstance(text_title, str): return matches
    logger.debug(f"Running fuzzy match for source_id={source_id}, title='{text_title[:50]}...'")
    try:
        sql = f"""
            SELECT asset_id, name, levenshtein(LOWER(name), LOWER(?)) as dist
            FROM {db.ASSETS_TABLE} WHERE dist <= ? ORDER BY dist LIMIT 5;
        """
        for asset_id, asset_name, dist in con.sql(sql, [text_title, threshold]).fetchall():
            matches.append((source_id, asset_id, float(dist)))
            logger.info(f"Fuzzy match found: source_id={source_id} -> asset_id={asset_id} (Name: '{asset_name}', Distance: {dist})")
    except Exception as e: logger.error(f"Error during fuzzy match query for source_id={source_id}: {e}")
    return matches

async def resolve_vector(source_id: str, text_content: str, con: duckdb.DuckDBPyConnection, threshold: float = 0.25, limit: int = 3) -> List[Tuple[str, int, float]]:
    """Stage 3: Semantic matching using Vector Similarity Search (VSS)."""
    matches = []
    if not openai_client or not text_content or not isinstance(text_content, str): return matches
    logger.debug(f"Running vector match for source_id={source_id}")
    try:
        con.sql("SELECT vss_version();") # Check if VSS extension is loaded
        query_embedding = await get_openai_embedding(text_content)
        if not query_embedding:
            logger.warning(f"Could not generate embedding for input source_id={source_id}, skipping vector search.")
            return matches
        sql = f"""
            SELECT asset_id, array_cosine_distance(embedding, ?) AS distance
            FROM {db.ASSET_EMBEDDINGS_TABLE} WHERE distance < ? ORDER BY distance LIMIT ?;
        """
        params = [query_embedding, threshold, limit]
        for asset_id, distance in con.sql(sql, params).fetchall():
            matches.append((source_id, asset_id, float(distance)))
            logger.info(f"Vector match found: source_id={source_id} -> asset_id={asset_id} (Distance: {distance:.4f})")
    except duckdb.CatalogException as e: logger.error(f"VSS extension likely not loaded or HNSW index missing: {e}")
    except APIError as e: logger.error(f"OpenAI API error during vector search embedding generation for source_id={source_id}: {e}")
    except Exception as e: logger.error(f"Error during vector match query for source_id={source_id}: {e}")
    return matches

# --- Storing ER Results ---

async def _store_er_links(
    source_id: str, source_id_name: str, link_table_name: str,
    results_dict: Dict[int, Dict[str, Any]], con: duckdb.DuckDBPyConnection
):
    """Helper function to store ER links in the appropriate table."""
    if not results_dict: return
    link_data = [(source_id, asset_id, match_info['method'], match_info['score'])
                 for asset_id, match_info in results_dict.items()]
    sql = f"""
        INSERT INTO {link_table_name} ({source_id_name}, asset_id, method, similarity_score)
        VALUES (?, ?, ?, ?) ON CONFLICT ({source_id_name}, asset_id, method) DO NOTHING;
    """
    try:
        con.executemany(sql, link_data)
        logger.info(f"Stored {len(link_data)} ER links for {source_id_name}={source_id} in {link_table_name}")
    except Exception as e:
        logger.error(f"Error storing ER links in {link_table_name} for {source_id_name}={source_id}: {e}")

# --- Main Resolution Pipeline ---

async def resolve_text_to_assets(
    source_id: str, source_type: str, text_content: str, text_title: Optional[str] = None,
    con: Optional[duckdb.DuckDBPyConnection] = None
) -> Dict[str, Any]:
    """Runs the full 3-stage entity resolution pipeline for a single text item from any source."""
    start_time = time.time()
    close_conn_locally = con is None
    if con is None: con = db.get_db_connection()

    if text_title is None and text_content: text_title = text_content[:100]

    results: Dict[int, Dict[str, Any]] = {}

    source_map = {
        "news": ("news_id", db.NEWS_ASSET_LINK_TABLE, db.NEWS_RAW_TABLE),
        "tweet": ("tweet_id", db.TWEET_ASSET_LINK_TABLE, db.TWEETS_TABLE),
        "reddit_post": ("post_id", db.REDDIT_POST_ASSET_LINK_TABLE, db.REDDIT_POSTS_TABLE),
        "wikimedia": ("page_id", db.WIKIMEDIA_ASSET_LINK_TABLE, db.WIKIMEDIA_CONTENT_TABLE),
        "stocktwits": ("message_id", db.STOCKTWITS_ASSET_LINK_TABLE, db.STOCKTWITS_MESSAGES_TABLE),
        "sec_filing": ("accession_number", db.SEC_FILING_ASSET_LINK_TABLE, db.SEC_FILINGS_TABLE),
        "ch_filing": ("transaction_id", db.CH_FILING_ASSET_LINK_TABLE, db.COMPANIES_HOUSE_FILINGS_TABLE),
        "uspto_patent": ("patent_number", db.USPTO_PATENT_ASSET_LINK_TABLE, db.USPTO_PATENTS_TABLE),
        "epo_patent": ("publication_number", db.EPO_PATENT_ASSET_LINK_TABLE, db.EPO_PATENTS_TABLE),
    }

    if source_type not in source_map:
        logger.error(f"Unsupported source_type '{source_type}' for entity resolution.")
        if close_conn_locally: db.close_db_connection()
        return {'source_id': source_id, 'source_type': source_type, 'matches': {}, 'processed_at': time.time()}

    source_id_name, link_table_name, _ = source_map[source_type]

    try:
        # Stage 1: Exact Match
        exact_matches = resolve_exact(source_id, text_content, con)
        for _, asset_id, score in exact_matches:
            if asset_id not in results: results[asset_id] = {'method': 'exact', 'score': score}

        # Stage 2: Fuzzy Match (Use title if available)
        if text_title and (not results or len(results) < 3):
            fuzzy_matches = resolve_fuzzy(source_id, text_title, con)
            for _, asset_id, score in fuzzy_matches:
                if asset_id not in results: results[asset_id] = {'method': 'fuzzy', 'score': score}

        # Stage 3: Vector Match (Use content)
        if text_content and (not results or len(results) < 3):
            await compute_and_store_asset_embeddings(con=con)
            vector_matches = await resolve_vector(source_id, text_content, con)
            for _, asset_id, score in vector_matches:
                 if asset_id not in results: results[asset_id] = {'method': 'vss', 'score': score}

        await _store_er_links(source_id, source_id_name, link_table_name, results, con)

    except Exception as e:
        logger.error(f"Error during resolution pipeline for {source_type} ID {source_id}: {e}")
    finally:
        if close_conn_locally and con: db.close_db_connection()

    end_time = time.time()
    logger.info(f"Resolution for {source_type} ID {source_id} completed in {end_time - start_time:.2f}s. Found {len(results)} matches.")
    return {'source_id': source_id, 'source_type': source_type, 'matches': results, 'processed_at': end_time}

# --- Wrapper functions for specific source types ---
# These functions would fetch the relevant text/title from the source table
# and then call the main resolve_text_to_assets function.

async def resolve_news_item(news_id: str, con: Optional[duckdb.DuckDBPyConnection] = None):
    # Fetch news title/body from news_raw table
    # Call resolve_text_to_assets(source_id=news_id, source_type='news', ...)
    logger.warning("resolve_news_item wrapper not fully implemented.")
    pass # Placeholder

async def resolve_tweet(tweet_id: str, con: Optional[duckdb.DuckDBPyConnection] = None):
    # Fetch tweet text from tweets_raw table
    # Call resolve_text_to_assets(source_id=tweet_id, source_type='tweet', ...)
    logger.warning("resolve_tweet wrapper not fully implemented.")
    pass # Placeholder

async def resolve_reddit_post(post_id: str, con: Optional[duckdb.DuckDBPyConnection] = None):
    # Fetch post title/selftext from reddit_posts table
    # Call resolve_text_to_assets(source_id=post_id, source_type='reddit_post', ...)
    logger.warning("resolve_reddit_post wrapper not fully implemented.")
    pass # Placeholder

# ... add similar wrappers for wikimedia, stocktwits, sec_filing, etc. ...

if __name__ == "__main__":
    import asyncio

    async def main():
        logger.info("Running ER example...")
        con = None
        try:
            con = db.get_db_connection()
            db.create_schema(con)

            logger.info("Checking/inserting dummy assets...")
            con.sql(f"""
                INSERT INTO {db.ASSETS_TABLE} (asset_id, name, isin, ticker, figi) VALUES
                (1, 'Apple Inc.', 'US0378331005', 'AAPL', 'BBG000B9XRY4'),
                (2, 'Microsoft Corporation', 'US5949181045', 'MSFT', NULL),
                (3, 'Tesla, Inc.', 'US88160R1014', 'TSLA', NULL),
                (4, 'Amazon.com, Inc.', 'US0231351067', 'AMZN', NULL),
                (5, 'NVIDIA Corporation', 'US67066G1040', 'NVDA', NULL)
                ON CONFLICT (asset_id) DO UPDATE SET
                    name=excluded.name, isin=excluded.isin, ticker=excluded.ticker, figi=excluded.figi;
            """)
            logger.info("Dummy assets checked/added.")

            await compute_and_store_asset_embeddings(asset_ids=[1, 2, 3, 4, 5], con=con)

            example_items = [
                {"id": "news1", "type": "news", "title": "Apple announces new iPhone", "content": "Apple Inc. today unveiled the latest iPhone model with advanced features."},
                {"id": "12345", "type": "tweet", "title": None, "content": "Watching the TSLA stock price today. Interesting moves. #Tesla"},
                {"id": "abcde", "type": "reddit_post", "title": "Microsoft earnings beat expectations", "content": "MSFT reported strong quarterly earnings, driven by cloud growth."},
                {"id": "amazon.com,_inc.", "type": "wikimedia", "title": "Amazon.com, Inc.", "content": "Amazon.com, Inc. is an American multinational technology company focusing on e-commerce, cloud computing, digital streaming, and artificial intelligence."},
                {"id": "111111111", "type": "stocktwits", "title": None, "content": "$NVDA looking strong ahead of earnings release."},
                {"id": "0001193125-23-255440", "type": "sec_filing", "title": "Apple Inc. 10-K", "content": "This is the text content extracted from an Apple 10-K filing document... focusing on financial performance and risk factors."},
                {"id": "xyz987", "type": "epo_patent", "title": "Patent for a new battery technology", "content": "Abstract describing a novel electrode composition for lithium-ion batteries, potentially relevant to Tesla or other EV makers."},
                {"id": "exact_figi_test", "type": "news", "title": "News about BBG000B9XRY4", "content": "Mentioning BBG000B9XRY4 directly in content."}
            ]

            for item in example_items:
                text_to_resolve = item["content"]
                title_for_fuzzy = item["title"] if item["title"] else text_to_resolve[:100]

                result = await resolve_text_to_assets(
                    source_id=item["id"],
                    source_type=item["type"],
                    text_content=text_to_resolve,
                    text_title=title_for_fuzzy,
                    con=con
                )
                print(f"--- Result for {item['type']} ID: {item['id']} ---")
                print(result.get('matches', {}))
                print("-" * 30)

        except Exception as e:
            logger.error(f"An error occurred in the ER example: {e}")
        finally:
            if con:
                db.close_db_connection()

    asyncio.run(main())
