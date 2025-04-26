# WealthArc Turbo ER 🚀

**Harvest public data, match entities, explore insights.**

This project demonstrates a rapid data harvesting and entity resolution pipeline designed to link external unstructured data (like news headlines) to structured asset records, built for the WealthArc hackathon.

It fetches data from various sources (financial APIs, news feeds, sanctions lists), stores it in a DuckDB database, and uses a three-stage entity resolution process (exact, fuzzy, semantic) to connect the dots. A Streamlit application provides an interactive demo.

## Features

*   **Data Ingestion:** Pulls data from OpenFIGI, Finnhub, NewsAPI, OFAC SDN, and more (extensible).
*   **Storage:** Uses DuckDB (`wa.db`) for both raw API payloads and cleaned, structured tables.
*   **Entity Resolution:**
    1.  **Exact Match:** Links based on ISIN, CUSIP, FIGI, Ticker, etc.
    2.  **Fuzzy Match:** Uses Levenshtein distance for name similarity.
    3.  **Semantic Match:** Employs OpenAI embeddings (`text-embedding-3-small`) and DuckDB's VSS extension for meaning-based linking.
*   **Demo UI:** A Streamlit application (`streamlit_app.py`) allows triggering data pulls, observing ER matches, and exploring basic asset data.
*   **Demo Notebook:** A Jupyter notebook (`demo.ipynb`) showcases key functionalities programmatically.

## Project Structure

```
wealtharc-turbo-er/
├─ README.md
├─ pyproject.toml        # Poetry config
├─ poetry.lock
├─ .gitignore
├─ wa/                   # Python package source
│  ├─ __init__.py
│  ├─ config.py          # Config loader (uses .env)
│  ├─ db.py              # DuckDB setup, schema, VSS
│  ├─ er.py              # 3-stage Entity Resolution logic
│  ├─ ingest/            # Data source ingestion modules
│  │   ├─ __init__.py
│  │   ├─ figi.py
│  │   ├─ finnhub.py
│  │   ├─ newsapi.py
│  │   └─ ofac.py
│  │   └─ ... (others can be added)
│  └─ demo/              # Demo scripts and notebooks
│      ├─ __init__.py
│      ├─ bootstrap.py     # DB seeding script
│      ├─ streamlit_app.py # Streamlit UI
│      └─ demo.ipynb       # Jupyter demo notebook (to be created)
├─ requirements.txt      # Exported dependencies
└─ logs/                 # Log files (created automatically)
└─ .env                  # API Keys (create this file!)
```

## Setup

1.  **Prerequisites:**
    *   Python 3.11+
    *   Poetry (`pip install poetry`)

2.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd wealtharc-turbo-er
    ```

3.  **Create `.env` file:**
    Copy the example below into a new file named `.env` in the project root (`wealtharc-turbo-er/`) and fill in your API keys.
    ```dotenv
    # --- General ---
    # DUCKDB_FILE=wa.db # Optional: Override default DB name
    # LOG_LEVEL=DEBUG   # Optional: Set to DEBUG for more verbose logs

    # --- Required API Keys ---
    OPENAI_API_KEY="sk-..."
    NEWSAPI_API_KEY="..."
    FINNHUB_API_KEY="..."

    # --- Optional API Keys (Needed for corresponding ingestors) ---
    OPENFIGI_API_KEY="..." # Recommended for higher rate limits
    # IEXCLOUD_API_KEY="..."
    # ALPHAVANTAGE_API_KEY="..."
    # FRED_API_KEY="..."
    # OPENEXCHANGERATES_APP_ID="..."
    # EIA_API_KEY="..."
    # QUANDL_API_KEY="..."
    # ESG_BOOK_API_KEY="..." # Or token
    # TWITTER_BEARER_TOKEN="..."
    # REDDIT_CLIENT_ID="..."
    # REDDIT_CLIENT_SECRET="..."
    # REDDIT_USER_AGENT="MyApp/0.1 by YourUsername"
    # SEC_EDGAR_USER_AGENT="Your Name YourEmail@example.com" # Required by SEC EDGAR
    # UK_COMPANIES_HOUSE_API_KEY="..."
    # USPTO_API_KEY="..."
    # EPO_OPS_KEY="..."
    # EPO_OPS_SECRET="..."
    ```
    *   **Critical Keys:** `OPENAI_API_KEY`, `NEWSAPI_API_KEY`, `FINNHUB_API_KEY` are needed for the core demo functionality.

4.  **Install dependencies:**
    ```bash
    poetry install
    ```

5.  **Bootstrap the database:**
    This command creates the `wa.db` file, sets up the schema, adds 5 sample assets (Apple, Microsoft, Tesla, Amazon, NVIDIA), computes their embeddings, and fetches ~20 recent news headlines and quotes.
    ```bash
    poetry run python -m wa.demo.bootstrap
    ```
    *(Requires `OPENAI_API_KEY`, `NEWSAPI_API_KEY`, `FINNHUB_API_KEY` to be set in `.env`)*

## Running the Demo

1.  **Streamlit Application:**
    Launch the interactive web UI:
    ```bash
    poetry run streamlit run wa/demo/streamlit_app.py
    ```
    Navigate the tabs to pull data, manually resolve text, and explore assets.

2.  **Jupyter Notebook:**
    *(Notebook `demo.ipynb` still needs to be created)*
    Launch JupyterLab:
    ```bash
    poetry run jupyter lab
    ```
    Open and run the cells in `wa/demo/demo.ipynb`.

## Diagram (Placeholder)

```mermaid
graph LR
    subgraph InputSources [Data Sources]
        NewsAPI --> P[Pipeline]
        Finnhub --> P
        OpenFIGI --> P
        OFAC --> P
        OtherAPIs[...] --> P
    end

    subgraph Pipeline [Ingestion & ER Pipeline]
        direction TB
        P[Ingestor] -- Raw Data --> DB[(DuckDB wa.db<br/>raw_*, clean_*)]
        DB -- Assets --> ER{Entity Resolution}
        P -- News/Tweets etc. --> ER
        ER -- Links --> DB
        subgraph ER [Entity Resolution Stages]
         direction TB
         ER_Exact[1. Exact Match<br/>(ISIN, FIGI...)] --> ER_Fuzzy
         ER_Fuzzy[2. Fuzzy Match<br/>(Levenshtein)] --> ER_VSS
         ER_VSS[3. Semantic Match<br/>(Embeddings + VSS)]
        end
    end

    subgraph Output [Demo & Exploration]
     direction TB
     DB --> Streamlit[Streamlit App]
     DB --> Notebook[Jupyter Notebook]
    end

    style DB fill:#D4F1F4,stroke:#05445E
    style ER fill:#E8E8E8,stroke:#333
```

## Demo GIF (Placeholder)

*[Link to Demo GIF showing Streamlit app interaction will be added here]*
