# System Patterns

## Architecture

The system follows a simple service-oriented pattern:

1.  **Docker Environment:** Docker (`Dockerfile`) defines the base image, installs dependencies (including Python, pip, and potentially browser binaries/drivers like Chromium), and copies the application code. `docker-compose.yml` orchestrates the service(s), manages networking, volumes, and environment variables.
2.  **API Service (`app.py`):** A Python web application (likely Flask or FastAPI based on `app.py`) runs inside the container. It listens for incoming HTTP requests on a specified port.
3.  **Browser Automation Logic:** Upon receiving a request, the API service invokes a browser automation library (e.g., Pyppeteer, Selenium) to launch and control a headless browser instance *within the same container*.
4.  **Request/Response Flow:** The API receives task parameters (URL, actions) in the request, executes the browser task, and returns a response (status, results) to the caller.

```mermaid
graph LR
    User -->|HTTP Request| APIService(API Service / app.py);
    User -->|HTTP Request /api/v1/...| APIService(FastAPI Service / app.py);
    APIService -->|Selects LLM (Langchain)| LLMProvider(OpenAI/Anthropic/etc.);
    APIService -->|Creates Task & Config| TaskManager(In-Memory Dict);
    APIService -->|Uses browser-use Agent| BrowserUseAgent(browser_use.Agent);
    BrowserUseAgent -->|Uses browser-use Browser| BrowserUseBrowser(browser_use.Browser);
    BrowserUseBrowser -->|Controls (Playwright)| HeadlessBrowser(Headless Browser);
    BrowserUseAgent -->|Calls| LLMProvider;
    BrowserUseAgent -->|Updates| TaskManager;
    APIService -->|HTTP Response| User;

    subgraph Docker Container [Runs as appuser]
        APIService
        TaskManager
        BrowserUseAgent
        BrowserUseBrowser
        HeadlessBrowser
        LLMProvider [Interacts externally]
    end

    subgraph Host Machine
        Port24006[Host Port 24006] <--> APIService[Container Port 8000];
        LocalData[./data Volume] <--> ContainerData[/app/data];
        EnvVarsOrDotEnv[.env File / Host Env] --> APIService;
    end
```

*Note: This service acts as an API bridge, allowing external users (or services like n8n) to trigger browser automation tasks driven by LLMs (via Langchain and the `browser-use` library). It manages tasks, interacts with configured LLM providers, and controls a headless browser.*

## Key Technical Decisions (Confirmed/Inferred)

-   **Language:** Python 3.11 (confirmed by `Dockerfile`).
-   **Web Framework:** FastAPI with Uvicorn server (confirmed).
-   **Task Management:** In-memory dictionary, asynchronous execution via `asyncio`. Task lifecycle managed (create, run, pause, resume, stop).
-   **Containerization:** Docker and Docker Compose (confirmed).
-   **Browser Automation:** Uses the `browser-use` library (`Agent`, `Browser`, `BrowserConfig`) which wraps Playwright (confirmed).
-   **LLM Integration:** Uses Langchain (`langchain-*` packages) to connect to various LLM providers (OpenAI, Anthropic, MistralAI, Google, Ollama, Azure), selected via API request (`ai_provider`).
-   **Headless Operation:** Default headless, configurable via `BROWSER_USE_HEADFUL` env var or `headful` task parameter.
-   **Networking:** Exposes port `8000` internally, mapped to `24006` externally (confirmed). Includes `/api/v1/ping` healthcheck.
-   **Security:** Runs as non-root user `appuser`. Relies on environment variables for sensitive API keys (`.env` or host). Custom Chrome path/user-data only configurable via env vars.
-   **Configuration:** `python-dotenv` loads `.env`. Numerous env vars for LLMs, port, logging, browser behavior.
-   **Data Persistence:** Mounts host `./data` to container `/app/data`. Task results, steps, errors stored in-memory. Optional cookie saving (`save_browser_data`).

## Component Relationships

-   `docker-compose.yml` (`version: '3'`):
    -   Defines the service named `browser-n8n-bridge`.
    -   Builds the image using the current directory context and `Dockerfile`.
    -   Maps host port `24006` to container port `8000`.
    -   Injects numerous environment variables (LLM API keys, model IDs, `PORT`, `LOG_LEVEL`, `BROWSER_USE_HEADFUL`). Relies heavily on host environment or `.env` file for secrets.
    -   Mounts local `./data` directory to `/app/data` inside the container for persistence.
    -   Sets restart policy to `unless-stopped`.
    -   Defines a healthcheck (similar to Dockerfile's) targeting `http://localhost:8000/api/v1/ping` with a `start_period`.
-   `Dockerfile`:
    -   Uses `python:3.11-slim` base image.
    -   Installs system dependencies (`apt-get`) and Python packages (`pip`).
    -   Installs Playwright browsers (`playwright install`).
    -   Copies application code.
    -   Sets up `/app/data` directory.
    -   Exposes port 8000.
    -   Configures a non-root user (`appuser`).
    -   Includes a `HEALTHCHECK` command targeting `/api/v1/ping`.
    -   Runs `app.py` as the entrypoint.
-   `app.py`: Core FastAPI application.
    -   Defines API endpoints (`/api/v1/run-task`, `/status`, `/task`, `/stop`, `/pause`, `/resume`, `/list`, `/ping`, `/browser-config`, `/live/{task_id}`).
    -   Uses `browser_use.Agent` to execute tasks based on instructions.
    -   Uses Langchain to instantiate LLMs (`get_llm` function).
    -   Manages task state (status, results, errors, steps) in an in-memory dictionary (`tasks`).
    -   Handles browser configuration (headless/headful, custom Chrome paths via env vars).
    -   Provides a basic live HTML view (`/live/{task_id}`).
-   `browser-use` library: Handles the interaction between the LLM agent and the Playwright browser.
-   `requirements.txt`: Specifies Python dependencies (FastAPI, Uvicorn, Pydantic, python-dotenv, browser-use, Langchain packages, asyncio).
-   `.env` / `.env-example`: Hold configuration, primarily sensitive API keys and optional browser settings (`CHROME_PATH`, `CHROME_USER_DATA`, `BROWSER_USE_HEADFUL`).
