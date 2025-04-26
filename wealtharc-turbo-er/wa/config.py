import os
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

# Load environment variables from .env file
# The .env file should be placed in the project root directory (wealtharc-turbo-er/)
dotenv_path = Path(__file__).parent.parent / '.env'
if dotenv_path.exists():
    logger.info(f"Loading environment variables from: {dotenv_path}")
    load_dotenv(dotenv_path=dotenv_path)
else:
    logger.warning(f".env file not found at {dotenv_path}. API keys might be missing.")

# --- General Config ---
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / os.getenv("DUCKDB_FILE", "wa.db")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# --- API Keys ---
# It's crucial to set these in your .env file
OPENFIGI_API_KEY = os.getenv("OPENFIGI_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
IEXCLOUD_API_KEY = os.getenv("IEXCLOUD_API_KEY") # May require paid plan for some data
ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")
FRED_API_KEY = os.getenv("FRED_API_KEY") # Needed for many series
OPENEXCHANGERATES_APP_ID = os.getenv("OPENEXCHANGERATES_APP_ID")
EIA_API_KEY = os.getenv("EIA_API_KEY")
QUANDL_API_KEY = os.getenv("QUANDL_API_KEY")
ESG_BOOK_API_KEY = os.getenv("ESG_BOOK_API_KEY") # Or use token-based auth
NEWSAPI_API_KEY = os.getenv("NEWSAPI_API_KEY")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN") # Twitter API v2
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "WealthArcTurboER/0.1 by Cline")
SEC_EDGAR_USER_AGENT = os.getenv("SEC_EDGAR_USER_AGENT", "Your Name Your Email") # Required by SEC
UK_COMPANIES_HOUSE_API_KEY = os.getenv("UK_COMPANIES_HOUSE_API_KEY")
USPTO_API_KEY = os.getenv("USPTO_API_KEY") # If needed for specific APIs
EPO_OPS_KEY = os.getenv("EPO_OPS_KEY") # Consumer key
EPO_OPS_SECRET = os.getenv("EPO_OPS_SECRET") # Consumer secret

# --- OpenAI API Key ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
OPENAI_EMBEDDING_DIMENSIONS = 1536 # Dimension for text-embedding-3-small

# --- Defaults & Settings ---
HTTPX_TIMEOUT = 30.0 # Default timeout for HTTP requests
DEFAULT_USER_AGENT = "WealthArcTurboER/0.1 (https://github.com/your-repo; mailto:your-email)" # Generic UA

# --- Logging Setup ---
logger.add(
    PROJECT_ROOT / "logs" / "wa_turbo_er_{time}.log",
    rotation="10 MB",
    retention="10 days",
    level=LOG_LEVEL,
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"
)

logger.info("Configuration loaded.")
logger.info(f"Database path: {DB_PATH}")

# --- Input Validation (Optional but Recommended) ---
# Example: Check if critical API keys are present
# if not OPENFIGI_API_KEY:
#     logger.critical("OPENFIGI_API_KEY is not set in the environment or .env file!")
# if not FINNHUB_API_KEY:
#     logger.critical("FINNHUB_API_KEY is not set in the environment or .env file!")
# if not NEWSAPI_API_KEY:
#     logger.critical("NEWSAPI_API_KEY is not set in the environment or .env file!")
# if not OPENAI_API_KEY:
#     logger.critical("OPENAI_API_KEY is not set in the environment or .env file!")

# You can add more checks for other required keys
