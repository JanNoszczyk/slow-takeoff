# Project Brief

## Core Goal

The primary goal of this project is to provide a **local bridge service** that allows **n8n** (or other clients) to interact with the **`browser-use` Python library** via a Docker container. It aims to mimic the Browser Use Cloud API endpoints locally.

## Key Requirements

1.  **Dockerization:** Containerize the Python application (`app.py`), `browser-use` library, Playwright browsers, and dependencies using Docker and Docker Compose.
2.  **Browser Automation:** Leverage the `browser-use` library (which uses Playwright) to perform LLM-driven browser tasks based on natural language instructions.
3.  **API Interface:** Expose a FastAPI application mimicking the Browser Use Cloud API endpoints for task management (run, status, stop, pause, resume, list).
4.  **LLM Integration:** Integrate with multiple LLM providers (OpenAI, Anthropic, Mistral, Google, Ollama, Azure) via Langchain, configurable through environment variables.
5.  **Configuration:** Manage configuration (API keys, browser settings, port, logging) primarily via environment variables (`.env` file).
6.  **Reproducibility:** Ensure the service is easily runnable using `docker-compose up`.

## Scope (Confirmed)

-   `Dockerfile` setup with Python 3.11, system dependencies, Python requirements, and Playwright browser installation.
-   `docker-compose.yml` defining the `browser-n8n-bridge` service, port mapping (24006:8000), volume mount (`./data`), and environment variable injection.
-   `app.py` implementing the FastAPI application with endpoints mimicking Browser Use Cloud API.
-   Integration of `browser_use.Agent` for task execution.
-   Integration of Langchain for multi-LLM support.
-   Configuration loading via `python-dotenv`.
-   Basic in-memory task management (status, results, steps).
-   Basic HTML live view for tasks.
-   `README.md` documenting purpose, setup (though focused on non-Docker), API, and configuration.

## Out of Scope (Initially)

-   Complex browser interaction workflows.
-   User interface for managing tasks.
-   Persistent storage of task results beyond basic logging or temporary files.
-   Advanced error handling and monitoring.
