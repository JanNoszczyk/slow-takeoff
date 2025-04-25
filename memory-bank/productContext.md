# Product Context

## Problem Solved

This project provides a **local alternative to the Browser Use Cloud API**, specifically targeted for use with **n8n** or similar workflow automation tools. It allows users to leverage the LLM-driven browser automation capabilities of the `browser-use` library within their own infrastructure, avoiding reliance on an external cloud service and potentially keeping data processing local. It addresses the need for integrating sophisticated browser interactions into automated workflows without managing browser dependencies directly in the workflow tool itself.

## How It Should Work

From the perspective of an n8n workflow (or other API client):

1.  **Start the Service:** The user starts the bridge service locally using `docker-compose up` after configuring necessary API keys in `.env`.
2.  **Configure n8n Node:** The user configures an n8n HTTP Request node (or equivalent) to point to the local bridge's endpoint (`http://localhost:24006/api/v1/...`).
3.  **Trigger Task via API:** The n8n workflow sends an HTTP POST request to `/api/v1/run-task` with the task instruction (e.g., "Log into example.com and check the dashboard") and the desired `ai_provider`.
4.  **Bridge Service Executes Task:** The bridge service (`app.py`) receives the request, selects the appropriate LLM via Langchain, initializes a `browser-use.Agent`, and runs the task asynchronously using Playwright in a headless browser within the container.
5.  **Monitor Status (Optional):** The n8n workflow can optionally poll the `/api/v1/task/{task_id}/status` endpoint to track progress.
6.  **Retrieve Result:** Once the task status is `finished` (or `failed`), the n8n workflow can retrieve the final result or error message from the status endpoint or the full task details endpoint (`/api/v1/task/{task_id}`).
7.  **Live View (Optional):** The user can monitor the task via the HTML live view at `/live/{task_id}`.

## User Experience Goals

-   **Simplicity:** Easy to set up and run with Docker.
-   **Reliability:** Consistent execution environment eliminates "works on my machine" issues.
-   **Control:** Clear API for triggering and managing tasks.
-   **Transparency:** Adequate logging to understand what the service is doing.
