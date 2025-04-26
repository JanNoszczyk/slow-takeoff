import duckdb
import time
from typing import List, Tuple, Optional, Dict, Any
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential
from openai import OpenAI, APIError
from async_lru import alru_cache

from wa import db, config

# Initialize OpenAI client
# Ensure OPENAI_API_KEY is set in the environment or .env file
if config.OPENAI_API_KEY:
    openai_client = OpenAI(api_key=config.OPENAI_API_KEY)
else:
    logger.warning("OPENAI_API_KEY not found. Vector Similarity Search (VSS) will not function.")
    openai_client = None

# --- Embedding Generation ---

@alru_cache(maxsize=1024) # Cache embeddings in memory for the duration of the run
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
async def get_openai_embedding(text: str, model: str = config.OPENAI_EMBEDDING_MODEL, dimensions: Optional[int] = config.OPENAI_EMBEDDING_DIMENSIONS) -> Optional[List[float]]:
    """
    Generates an embedding for the given text using OpenAI API with retries.
    Uses async_lru cache.
    """
    if not openai_client:
        logger.error("OpenAI client not initialized. Cannot generate embeddings.")
        return None
    if not text or not isinstance(text, str):
        logger.warning(f"Invalid input text for embedding: {text}")
        return None

    text = text.replace("\n", " ").strip() # OpenAI recommends replacing newlines
    if not text:
        logger.warning("Empty text after cleaning, cannot generate embedding.")
        return None

    try:
        logger.debug(f"Requesting OpenAI embedding for text (len={len(text)}): '{text[:100]}...'")
        params = {"input": [text], "model": model}
        if dimensions:
            params["dimensions"] = dimensions

        response = await openai_client.embeddings.create(**params)
        embedding = response.data[0].embedding
        logger.debug(f"Received embedding of dimension {len(embedding)}")
        return embedding
    except APIError as e:
        logger.error(f"OpenAI API error during embedding generation: {e}")
        raise # Reraise to trigger tenacity retry
    except Exception as e:
        logger.error(f"Unexpected error during embedding generation: {e}")
        raise # Reraise to potentially trigger retry or fail


async def compute_and_store_asset_embeddings(asset_ids: Optional[List[int]] = None, con: duckdb.DuckDBPyConnection = None):
    """
    Computes OpenAI embeddings for assets in the 'assets' table that don't have one yet
    and stores them in the 'asset_embeddings' table.

    Args:
        asset_ids: Optional list of specific asset_ids to process. If None, processes all missing.
        con: Optional DuckDB connection.
    """
    if not openai_client:
        logger.error("OpenAI client not initialized. Cannot compute asset embeddings.")
        return

    close_conn_locally = False
    if con is None:
        con = db.get_db_connection()
        close_conn_locally = True

    try:
        logger.info("Computing and storing missing asset embeddings...")

        # Query for assets missing embeddings
        base_query = """
            SELECT a.asset_id, a.name
            FROM assets a
            LEFT JOIN asset_embeddings ae ON a.asset_id = ae.asset_id
            WHERE ae.asset_id IS NULL AND a.name IS NOT NULL AND TRIM(a.name) != ''
        """
        if asset_ids:
             # Using IN operator requires careful handling of list formatting for SQL
            asset_id_list_str = ", ".join(map(str, asset_ids))
            query = f"{base_query} AND a.asset_id IN ({asset_id_list_str});"
        else:
            query = f"{base_query};"

        assets_to_embed = con.sql(query).fetchall()
        logger.info(f"Found {len(assets_to_embed)} assets requiring embeddings.")

        if not assets_to_embed:
            return

        insert_sql = f"""
            INSERT INTO asset_embeddings (asset_id, name, embedding, model_name)
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
        if close_conn_locally:
            db.close_db_connection()

# --- Entity Resolution Stages ---

def resolve_exact(text_id: str, text_content: str, con: duckdb.DuckDBPyConnection) -> List[Tuple[str, int, float]]:
    """
    Stage 1: Attempt to match text content against asset identifiers (ISIN, CUSIP, FIGI, Ticker).
    Returns a list of tuples: (text_id, matched_asset_id, similarity_score=1.0).
    """
    matches = []
    if not text_content or not isinstance(text_content, str):
        return matches

    logger.debug(f"Running exact match for text_id={text_id}")
    # Basic check for potential identifiers - could be improved with regex
    potential_ids = [word for word in text_content.split() if len(word) > 3 and len(word) < 20 and any(c.isalnum() for c in word)]

    if not potential_ids:
        return matches

    # Prepare identifiers for SQL query (handle potential duplicates)
    unique_ids = list(set(potential_ids))
    placeholders = ', '.join(['?'] * len(unique_ids))

    # Query assets table for exact matches on key identifiers
    sql = f"""
        SELECT asset_id
        FROM assets
        WHERE isin IN ({placeholders})
           OR cusip IN ({placeholders})
           OR figi IN ({placeholders})
           OR ticker IN ({placeholders})
           OR ric IN ({placeholders})
           OR wkn IN ({placeholders});
    """
    # Duplicate the unique_ids list for each field being checked
    params = unique_ids * 6 # Adjust count based on number of fields checked above

    try:
        matched_assets = con.sql(sql, params).fetchall()
        for (asset_id,) in matched_assets:
            matches.append((text_id, asset_id, 1.0)) # Exact match score is 1.0
            logger.info(f"Exact match found: text_id={text_id} -> asset_id={asset_id}")
    except Exception as e:
        logger.error(f"Error during exact match query for text_id={text_id}: {e}")

    return matches


def resolve_fuzzy(text_id: str, text_title: str, con: duckdb.DuckDBPyConnection, threshold: int = 4) -> List[Tuple[str, int, float]]:
    """
    Stage 2: Attempt fuzzy string matching between text title and asset names.
    Uses Levenshtein distance.
    Returns a list of tuples: (text_id, matched_asset_id, levenshtein_distance).
    """
    matches = []
    if not text_title or not isinstance(text_title, str):
        return matches

    logger.debug(f"Running fuzzy match for text_id={text_id}, title='{text_title[:50]}...'")
    try:
        # Query using Levenshtein distance - might be slow on large 'assets' table without optimization
        sql = f"""
            SELECT asset_id, name, levenshtein(LOWER(name), LOWER(?)) as dist
            FROM assets
            WHERE dist <= ?
            ORDER BY dist
            LIMIT 5; -- Limit potential fuzzy matches
        """
        matched_assets = con.sql(sql, [text_title, threshold]).fetchall()

        for asset_id, asset_name, dist in matched_assets:
            matches.append((text_id, asset_id, float(dist)))
            logger.info(f"Fuzzy match found: text_id={text_id} -> asset_id={asset_id} (Name: '{asset_name}', Distance: {dist})")
    except Exception as e:
        logger.error(f"Error during fuzzy match query for text_id={text_id}: {e}")

    return matches


async def resolve_vector(text_id: str, text_content: str, con: duckdb.DuckDBPyConnection, threshold: float = 0.25, limit: int = 3) -> List[Tuple[str, int, float]]:
    """
    Stage 3: Attempt semantic matching using Vector Similarity Search (VSS).
    Requires asset embeddings to be pre-computed.
    Returns a list of tuples: (text_id, matched_asset_id, cosine_distance).
    """
    matches = []
    if not openai_client:
        logger.warning("OpenAI client not available, skipping vector search.")
        return matches
    if not text_content or not isinstance(text_content, str):
        return matches

    logger.debug(f"Running vector match for text_id={text_id}")
    try:
        # Check if VSS extension is loaded - basic check
        con.sql("SELECT vss_version();")

        # 1. Get embedding for the input text
        query_embedding = await get_openai_embedding(text_content)
        if not query_embedding:
            logger.warning(f"Could not generate embedding for input text_id={text_id}, skipping vector search.")
            return matches

        # 2. Perform VSS query using array_cosine_distance (lower is better)
        # Assumes 'asset_embeddings' table has an HNSW index named 'asset_hnsw_idx'
        sql = f"""
            SELECT asset_id, array_cosine_distance(embedding, ?) AS distance
            FROM asset_embeddings
            WHERE distance < ?
            ORDER BY distance
            LIMIT ?;
        """
        params = [query_embedding, threshold, limit]
        matched_assets = con.sql(sql, params).fetchall()

        for asset_id, distance in matched_assets:
            matches.append((text_id, asset_id, float(distance)))
            logger.info(f"Vector match found: text_id={text_id} -> asset_id={asset_id} (Distance: {distance:.4f})")

    except duckdb.CatalogException as e:
        logger.error(f"VSS extension likely not loaded or HNSW index missing for vector search: {e}")
    except APIError as e:
        logger.error(f"OpenAI API error during vector search embedding generation for text_id={text_id}: {e}")
    except Exception as e:
        logger.error(f"Error during vector match query for text_id={text_id}: {e}")

    return matches


async def resolve_text_to_assets(text_id: str, text_content: str, text_title: Optional[str] = None, con: duckdb.DuckDBPyConnection = None) -> Dict[str, Any]:
    """
    Runs the full 3-stage entity resolution pipeline for a single text item.

    Args:
        text_id: Unique identifier for the text item (e.g., news URL hash, tweet ID).
        text_content: The main body of text to use for matching (especially vector).
        text_title: The title of the text (used primarily for fuzzy matching).
        con: Optional DuckDB connection.

    Returns:
        A dictionary containing the resolution results:
        {
            'text_id': str,
            'matches': {
                asset_id: {'method': str, 'score': float},
                ...
            },
            'processed_at': timestamp
        }
    """
    start_time = time.time()
    close_conn_locally = False
    if con is None:
        con = db.get_db_connection()
        close_conn_locally = True

    if text_title is None:
        text_title = text_content[:100] # Use first 100 chars of content if no title

    results: Dict[int, Dict[str, Any]] = {} # Stores best match per asset_id: {asset_id: {'method': '...', 'score': ...}}

    try:
        # --- Stage 1: Exact Match ---
        exact_matches = resolve_exact(text_id, text_content, con)
        for _, asset_id, score in exact_matches:
            if asset_id not in results:
                results[asset_id] = {'method': 'exact', 'score': score}

        # --- Stage 2: Fuzzy Match ---
        # Only run if no exact matches or to supplement
        if not results or len(results) < 3 : # Example condition: run fuzzy if fewer than 3 exact matches
            fuzzy_matches = resolve_fuzzy(text_id, text_title, con)
            for _, asset_id, score in fuzzy_matches:
                if asset_id not in results: # Add only if not already matched by exact
                    results[asset_id] = {'method': 'fuzzy', 'score': score}

        # --- Stage 3: Vector Match ---
        # Only run if needed and embeddings are available
        if not results or len(results) < 3: # Example condition: run VSS if fewer than 3 total matches so far
             # Ensure embeddings exist for assets before attempting VSS
            await compute_and_store_asset_embeddings(con=con) # Compute any missing embeddings first
            vector_matches = await resolve_vector(text_id, text_content, con)
            for _, asset_id, score in vector_matches:
                 if asset_id not in results: # Add only if not already matched
                    results[asset_id] = {'method': 'vss', 'score': score}

        # --- Store Links ---
        if results:
            link_sql = """
                INSERT INTO news_asset_link (news_id, asset_id, method, similarity_score)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (news_id, asset_id, method) DO NOTHING;
            """
            link_data = [
                (text_id, asset_id, match_info['method'], match_info['score'])
                for asset_id, match_info in results.items()
            ]
            con.executemany(link_sql, link_data)
            logger.info(f"Stored {len(link_data)} ER links for text_id={text_id}")

    except Exception as e:
        logger.error(f"Error during resolution pipeline for text_id={text_id}: {e}")
    finally:
        if close_conn_locally:
            db.close_db_connection()

    end_time = time.time()
    logger.info(f"Resolution for text_id={text_id} completed in {end_time - start_time:.2f}s. Found {len(results)} matches.")

    return {
        'text_id': text_id,
        'matches': results,
        'processed_at': time.time()
    }


if __name__ == "__main__":
    # Example Usage (requires .env file with OPENAI_API_KEY and DuckDB setup)
    import asyncio

    async def main():
        logger.info("Running ER example...")
        con = None
        try:
            con = db.get_db_connection()
            db.create_schema(con) # Ensure schema exists

            # 1. Add some dummy assets if they don't exist
            logger.info("Checking/adding dummy assets...")
            con.sql("""
                INSERT INTO assets (asset_id, name, isin, ticker) VALUES
                (1, 'Apple Inc.', 'US0378331005', 'AAPL'),
                (2, 'Microsoft Corporation', 'US5949181045', 'MSFT'),
                (3, 'Tesla, Inc.', 'US88160R1014', 'TSLA'),
                (4, 'Amazon.com, Inc.', 'US0231351067', 'AMZN'),
                (5, 'NVIDIA Corporation', 'US67066G1040', 'NVDA')
                ON CONFLICT (asset_id) DO NOTHING;
            """)
            logger.info("Dummy assets checked/added.")

            # 2. Ensure embeddings are computed for these assets
            await compute_and_store_asset_embeddings(asset_ids=[1, 2, 3, 4, 5], con=con)

            # 3. Example Texts
            example_texts = [
                {"id": "news1", "title": "Apple announces new iPhone", "content": "Apple Inc. today unveiled the latest iPhone model with advanced features."},
                {"id": "news2", "title": "MSFT earnings beat expectations", "content": "Microsoft reported strong quarterly earnings, driven by cloud growth."},
                {"id": "tweet1", "title": None, "content": "Watching the TSLA stock price today. Interesting moves. #Tesla"},
                {"id": "news3", "title": "Is Amazon Overvalued?", "content": "Analysts debate AMZN's current stock valuation after its recent rally."},
                {"id": "random1", "title": "Weather forecast for California", "content": "Sunny skies expected in most parts of California this week."},
                {"id": "exact1", "title": "FIGI BBG000B9XRY4 News", "content": "Some news mentioning FIGI BBG000B9XRY4 directly"} # Assuming BBG000B9XRY4 is Apple's FIGI
            ]

            # Manually add Apple's FIGI for the exact match test
            try:
                con.sql("UPDATE assets SET figi = 'BBG000B9XRY4' WHERE asset_id = 1;")
            except Exception as e:
                logger.warning(f"Could not update FIGI for Apple: {e}")


            # 4. Resolve each text
            for text_item in example_texts:
                result = await resolve_text_to_assets(
                    text_id=text_item["id"],
                    text_content=text_item["content"],
                    text_title=text_item["title"],
                    con=con
                )
                print(f"--- Result for {text_item['id']} ---")
                print(result)
                print("-" * (len(text_item['id']) + 14))


        except Exception as e:
            logger.error(f"An error occurred in the example: {e}")
        finally:
            if con:
                db.close_db_connection()

    # Run the async main function
    asyncio.run(main())
