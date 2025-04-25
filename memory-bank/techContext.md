# Tech Context

## Technologies Used

-   **Programming Language:** Python 3.11 (confirmed by `Dockerfile`).
-   **Web Framework:** FastAPI with Uvicorn server (confirmed by `requirements.txt`).
-   **Browser Automation Library:** Playwright (confirmed by `Dockerfile`), likely utilized via the `browser-use` package (from `requirements.txt`).
-   **LLM Integration Framework:** Langchain, supporting OpenAI, Anthropic, MistralAI, Google GenAI, Ollama, Azure OpenAI (confirmed by `app.py` and `requirements.txt`).
-   **Containerization:** Docker, Docker Compose (confirmed).
-   **Operating System (Base Image):** Debian (based on `python:3.11-slim` image).
-   **Dependency Management:** `pip` and `requirements.txt` for Python; `apt-get` for system.
-   **Schema Validation:** Pydantic (confirmed).
-   **Environment Variables:** `python-dotenv` loads `.env` (confirmed).
-   **Asynchronous Operations:** `asyncio` used for background task execution (confirmed).
-   **API:** FastAPI providing RESTful endpoints.

## Development Setup

1.  **Prerequisites:** Docker and Docker Compose.
2.  **Configuration:** Primarily via environment variables (loaded from `.env` or host) for LLM API keys, model IDs, browser behavior (`BROWSER_USE_HEADFUL`, `CHROME_PATH`, `CHROME_USER_DATA`), logging (`LOG_LEVEL`), and port (`PORT`).
3.  **Running the Service:** `docker-compose up`.
4.  **Accessing the Service:** API available at `http://localhost:24006/api/v1/...`. Live view at `http://localhost:24006/live/{task_id}`.
5.  **Persistence:** Host `./data` mapped to container `/app/data`. Task state itself (status, results, steps) is stored in-memory and lost on restart. Optional browser cookie saving to in-memory task data.
6.  **Restart Policy:** `unless-stopped`.
7.  **Health Check:** Checks `/api/v1/ping`.
8.  **Testing:** `test_api.py` likely targets `http://localhost:24006`.
9.  **API Endpoints:**
    -   `POST /api/v1/run-task`: Starts a new browser task. Takes `task` (instruction), optional `ai_provider`, `save_browser_data`, `headful`, `use_custom_chrome`. Returns `TaskResponse` (id, status, live_url).
    -   `GET /api/v1/task/{task_id}/status`: Gets current task status, result/error. Returns `TaskStatusResponse`.
    -   `GET /api/v1/task/{task_id}`: Gets full task details (excluding agent object).
    -   `PUT /api/v1/stop-task/{task_id}`: Stops a running task.
    -   `PUT /api/v1/pause-task/{task_id}`: Pauses a running task.
    -   `PUT /api/v1/resume-task/{task_id}`: Resumes a paused task.
    -   `GET /api/v1/list-tasks`: Lists summaries of all tasks.
    -   `GET /api/v1/ping`: Health check.
    -   `GET /api/v1/browser-config`: Shows current effective browser configuration (from env vars).
    -   `GET /live/{task_id}`: HTML page for live task view (uses polling).
9.  **Testing Script (`test_api.py`):** Provides a CLI tool to run a task, poll status, and print results. Requires `--url http://localhost:24006` when targeting the Docker container. Accepts `--task`, `--provider`, and `--headful` arguments.

## Technical Constraints

-   **Headless Environment:** Default is headless. Can be overridden globally by `BROWSER_USE_HEADFUL=true` env var or per task via the `headful` request parameter. Custom Chrome instances (`CHROME_PATH`, `CHROME_USER_DATA`) can only be set via environment variables.
-   **Resource Limits:** Standard container resource considerations apply.
-   **Network Access:** Container requires outbound access for LLM APIs and target websites.
-   **Dependency Installation:** Handled by `Dockerfile`.
-   **Execution Environment:** Runs as non-root `appuser`.
-   **Data Directory:** `/app/data` mapped to host `./data`. Purpose within `browser-use` not fully clear, potentially for screenshots or downloads during tasks.
-   **Port:** Container 8000 mapped to host 24006.
-   **Configuration Management:** Primarily via environment variables/.env. Sensitive API keys needed.
-   **State Management:** Task state is volatile (in-memory). No persistence of task list or detailed results across restarts, only files potentially saved in `./data`.

## Dependencies

-   **Python Packages:** Key packages listed in `requirements.txt`: `fastapi`, `uvicorn`, `pydantic`, `python-dotenv`, `browser-use`, `langchain-openai`, `langchain-anthropic`, `langchain-mistralai`, `langchain-google-genai`, `langchain-ollama`, `asyncio`.
-   **System Packages:** Defined in `Dockerfile` via `apt-get`. Includes `wget`, `gnupg`, `ca-certificates`, `procps`, `unzip`, and various `lib*` packages required by Playwright/browsers.
-   **Browser Binaries:** Installed via `playwright install` within the `Dockerfile`.
