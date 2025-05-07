# Technical Context

## Core Technologies

*   **Backend:** Python (version specified in `.python-version`). Key libraries include: `asyncio`, `pydantic`, `python-dotenv`, `agents` (custom SDK likely).
*   **Frontend (Original Dashboard):** Node.js, TypeScript, Next.js, React. Tailwind CSS is used (`tailwind.config.mjs`, `globals.css`). `@babel/standalone` is used for client-side TSX compilation (loaded via CDN).
*   **Frontend (Primary UI - NextChat):** Node.js, TypeScript, Next.js, React. Located in `/Users/jannoszczyk/Documents/Github/slow-takeoff/nextchat/`.
*   **Data Format:** JSON is used internally by `stonk_research_agent`. The `dashboard_agent` generates a TSX string. The original API route (`/api/generate-dashboard`) returns a JSON object `{ tsx: string, css: string }`. NextChat will receive MCP responses (potentially including TSX strings or other data formats from tools).
*   **MCP (Model Context Protocol):** Enabled in NextChat via `ENABLE_MCP=true` in `nextchat/.env.local`. MCP servers are configured in `nextchat/app/mcp/mcp_config.json`, specifying `command`, `args`, and `env` for each server. NextChat manages the lifecycle of these servers.

## Development Environment & Setup

*   **Python:** Uses a virtual environment (`.venv` directory present). `.python-version` suggests `pyenv` might be used for managing Python versions. Dependencies likely managed via `requirements.txt`.
*   **Original Frontend (`dashboard/`):** Node.js environment. Dependencies managed via `package.json`. Requires `tailwindcss` CLI.
*   **NextChat Frontend (`nextchat/`):** Node.js environment (>=18). Dependencies managed via `yarn.lock` / `package.json`.
*   **API Route Environment (Original Dashboard):** The environment running the Next.js API route needs Node.js, `npx`, access to `tailwindcss` CLI, and write permissions to the filesystem (`dashboard/temp` directory) for the dynamic Tailwind build process.
*   **Configuration (Project Root):** Environment variables (e.g., API keys for `stonk_research_agent`) are loaded using `python-dotenv` from a `.env` file (likely in the root `/Users/jannoszczyk/Documents/Github/slow-takeoff/.env`).
*   **Configuration (NextChat):** Specific NextChat configurations (like `OPENAI_API_KEY`, `ENABLE_MCP`) are in `nextchat/.env.local`. MCP server definitions are in `nextchat/app/mcp/mcp_config.json`.
*   **Containerization:** `Dockerfile` and `docker-compose.yml` exist for the original project. NextChat also has Docker deployment options (see its `README.md`).
*   **Running Locally:**
    *   Python Pipeline (Directly): `python run_pipeline.py "<query>"`
    *   Original Frontend Dashboard: `npm run dev` from within the `dashboard/` directory.
    *   NextChat UI: `yarn dev` from within the `nextchat/` directory (after ensuring MCP servers defined in its config are either running or can be spawned by it).
    *   MCP Servers (e.g., `stonk-research-mcp-server`, `wealthfront-mcp-server`): Started via `node /path/to/server/build/index.js`. NextChat can also manage spawning these if configured in `mcp_config.json`.

## Key Dependencies & Integrations

*   **Backend (Python Pipeline):**
    *   `stonk_research_agent`: Module for financial data gathering and analysis.
    *   `project_agents/dashboard_agent`: Module for generating TSX code for news display.
    *   `agents` SDK: Custom or third-party library used by agents.
*   **Backend (API Route - Node.js):**
    *   Executes Python pipeline (`run_pipeline.py`) via `child_process.spawn`.
    *   Uses Node.js `fs/promises` for temporary file I/O.
    *   Executes `tailwindcss` CLI via `npx` and `child_process.spawn`.
*   **External APIs/Services (used by `stonk_research_agent`):**
    *   (Same as before: OpenAI, Yahoo Finance, Finnhub, AlphaVantage, WebSearchTool, etc.)
*   **Frontend:**
    *   Calls the internal `/api/generate-dashboard` Next.js API route (GET) to fetch `{ tsx, css }` JSON.
    *   Uses `@babel/standalone` (via CDN and `window.Babel`) to compile the TSX string.
    *   Injects the received CSS string into a dynamic `<style>` tag.
    *   Renders the compiled React element.

## Technical Constraints & Considerations

*   **API Route Performance:** Running Python script + Tailwind CLI on every API request is a major performance bottleneck.
*   **API Route Environment:** Requires a specific environment setup (Node, npx, Tailwind CLI, write access) which might be complex or disallowed in some deployment scenarios (e.g., restrictive serverless).
*   **Tailwind CLI Execution:** Relies on `npx tailwindcss ...` executing correctly at runtime within the API route's environment. Path configurations (`tailwind.config.mjs`, input/output files) must be correct relative to the execution context (`dashboard/`).
*   **Security:** Runtime code compilation (Babel) and CSS injection need careful review. Ensure TSX/CSS from backend is trusted. Filesystem access in the API route needs appropriate permissions.
*   **Error Handling:** Robust error handling is needed for Python execution, file I/O, Tailwind execution, Babel compilation, and CSS injection.
*   **`@babel/standalone`:** Adds significant size to the initial frontend JavaScript load (used in original `dashboard/`).
*   **`@modelcontextprotocol/sdk`:** Likely used by NextChat internally (in `nextchat/app/mcp/`) for MCP communication.

## Version Control for Integrated Components

### NextChat Integration Strategy

*   **Context:** The `nextchat/` directory contains a clone of the `ChatGPTNextWeb/NextChat` repository, with local modifications made for this project.
*   **Problem:** Directly adding `nextchat/` (which contains its own `.git` directory) to the main `slow-takeoff` Git repository leads to an "embedded repository" issue. This doesn't properly track `nextchat`'s files and makes it difficult for collaborators or new clones to get the correct version.
*   **Recommended Solution: Fork & Git Submodule**
    1.  **Fork:** Create a personal fork of `ChatGPTNextWeb/NextChat` on GitHub (e.g., `YourGitHubUsername/NextChat`).
    2.  **Push Changes:** Push the local modifications from `slow-takeoff/nextchat/` to this new fork. This ensures your custom version of NextChat is stored in its own version-controlled repository.
    3.  **Prepare `slow-takeoff`:**
        *   In the `slow-takeoff` root, unstage the `nextchat` directory if it was previously added directly: `git rm --cached nextchat`.
        *   Delete the local `slow-takeoff/nextchat/` directory (once changes are safely on your fork).
    4.  **Add Submodule:** In the `slow-takeoff` root, add your fork as a Git submodule: `git submodule add <URL_of_your_fork> nextchat`.
    5.  **Commit:** Commit the new `.gitmodules` file and the `nextchat` submodule entry to the `slow-takeoff` repository.
*   **Benefits:** This approach correctly tracks a specific version (commit) of your customized NextChat fork within `slow-takeoff`. It keeps the NextChat history separate, allows for easier updates from the original `ChatGPTNextWeb/NextChat` (by pulling into your fork and then updating the submodule pointer in `slow-takeoff`), and is standard practice for managing modified third-party dependencies.
*   **Alternative (Not Recommended):** Absorbing `nextchat` files directly into `slow-takeoff` (by deleting `nextchat/.git`) simplifies the local structure but severs ties to the original project, losing its history and making updates very difficult.

*(This file outlines the tools and technical landscape of the project, based on projectbrief.md.)*
