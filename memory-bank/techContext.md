# Technical Context

## Core Technologies

*   **Backend:** Python (version specified in `.python-version`). Key libraries include: `asyncio`, `pydantic`, `python-dotenv`, `agents` (custom SDK likely).
*   **Frontend:** Node.js, TypeScript, Next.js, React. Tailwind CSS is used (`tailwind.config.mjs`, `globals.css`). `@babel/standalone` is used for client-side TSX compilation (loaded via CDN).
*   **Data Format:** JSON is used internally by `stonk_research_agent`. The `dashboard_agent` generates a TSX string. The API route (`/api/generate-dashboard`) returns a JSON object `{ tsx: string, css: string }` containing the agent's TSX and runtime-generated CSS.

## Development Environment & Setup

*   **Python:** Uses a virtual environment (`.venv` directory present). `.python-version` suggests `pyenv` might be used for managing Python versions. Dependencies likely managed via `requirements.txt`.
*   **Frontend:** Node.js environment. Dependencies managed via `package.json` (located in `dashboard/`). Requires `tailwindcss` CLI to be available (usually via `devDependencies`).
*   **API Route Environment:** The environment running the Next.js API route needs Node.js, `npx`, access to `tailwindcss` CLI, and write permissions to the filesystem (`dashboard/temp` directory) for the dynamic Tailwind build process.
*   **Configuration:** Environment variables (e.g., API keys) are loaded using `python-dotenv` from a `.env` file (likely in the root).
*   **Containerization:** `Dockerfile` and `docker-compose.yml` exist, indicating Docker support. The Docker environment would need to include all dependencies for both the Python pipeline and the Node.js API route's runtime Tailwind execution.
*   **Running Locally:**
    *   Python Pipeline (Directly): `python run_pipeline.py "<query>"`
    *   Frontend Dashboard: `npm run dev` from within the `dashboard/` directory.

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
*   **`@babel/standalone`:** Adds significant size to the initial frontend JavaScript load.

*(This file outlines the tools and technical landscape of the project, based on projectbrief.md.)*
