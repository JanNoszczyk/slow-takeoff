# System Patterns

## Architecture Overview

*   The system appears to consist of a Python backend pipeline and a Next.js frontend dashboard.
*   The frontend calls a backend API endpoint (`/api/generate-dashboard`) which in turn executes a Python script (`run_pipeline.py`).

```mermaid
graph LR
    A[Next.js Frontend] -->|GET /api/generate-dashboard?stockQuery=...| B(Next.js API Route);
    B -->|Executes| C(run_pipeline.py);
    C -->|Runs| D(stonk_research_agent);
    D -->|Returns Research Results (JSON)| C;
    C -->|Calls| E(dashboard_agent.run_tsx_generation);
    E -->|Generates TSX Code (String)| C;
    C -->|Prints TSX String| B;
    B -->|Writes TSX to temp file| B;
    B -->|Executes `npx tailwindcss` CLI| B;
    B -->|Reads generated CSS| B;
    B -->|Returns {tsx, css} JSON| A;
    A -->|Compiles TSX (Babel)| A;
    A -->|Injects CSS| A;
    A -->|Renders Compiled Element| A;
```

## Key Technical Decisions & Rationale

*   Utilizes separate Python backend logic (agents, pipeline) and a JavaScript/TypeScript frontend (Next.js). Rationale likely involves leveraging Python for data processing/AI and Next.js for modern web UI development.
*   **Dynamic Tailwind Build:** Due to issues applying Tailwind styles to runtime-generated TSX via `dangerouslySetInnerHTML` and user insistence on agent-generated TSX, the system now attempts a complex runtime Tailwind build.
    *   **Rationale:** To force Tailwind to generate CSS for classes used in the agent's output.
    *   **Mechanism:** The API route saves the agent's TSX, runs the Tailwind CLI against it, reads the resulting CSS, and sends both TSX and CSS to the frontend.
    *   **Concerns:** This approach has significant performance implications and adds complexity.
*   **Client-Side Compilation:** The frontend uses Babel Standalone (`@babel/standalone`) loaded via CDN to compile the received TSX string into executable JavaScript (React element creation calls) before rendering.
    *   **Rationale:** Required to render the TSX string as React components rather than inert HTML.
*   **Client-Side CSS Injection:** The frontend dynamically creates a `<style>` tag and injects the CSS received from the API route.
    *   **Rationale:** To make the runtime-generated Tailwind styles available to the browser for the compiled components.

## Core Components & Responsibilities

*   **`stonk_research_agent` (Python):** (Unchanged) Gathers stock-related information and produces structured research data.
*   **`project_agents/dashboard_agent` (Python):** (Unchanged) Generates Next.js TSX code strings for news display.
*   **`run_pipeline.py` (Python):** (Unchanged) Orchestrates agent calls and prints the final TSX code string to `stdout`.
*   **`dashboard/` (Next.js/TypeScript):** Frontend application.
    *   **API Route (`route.ts`):** Handles GET requests. Executes `run_pipeline.py`. Saves TSX output to a temporary file. Executes `npx tailwindcss` CLI to generate CSS based on the temporary TSX. Reads the generated CSS. Returns a JSON object `{ tsx: string, css: string }`. Manages temporary file creation and cleanup.
    *   **UI Page (`page.tsx`):** Fetches the `{ tsx, css }` JSON from the API. Uses Babel Standalone (via `window.Babel`) to compile the `tsx` string into a React element. Injects the `css` string into a `<style>` tag in the document head. Renders the compiled React element.
    *   **Layout (`layout.tsx`):** Includes the `<script>` tag to load `@babel/standalone` CDN.

## Design Patterns Utilized

*   **Agent Pattern:** Used for the `stonk_research_agent`.
*   **Pipeline Pattern:** Implemented in `run_pipeline.py`.
*   **API Route / Backend-for-Frontend (BFF):** The Next.js API route acts as an interface and orchestrator for the dynamic build process.
*   **Runtime Code Generation & Compilation:** The core (and problematic) pattern being attempted.

## Data Flow & Management

*   User initiates request via the Next.js frontend (`page.tsx`) by submitting a stock query.
*   Frontend makes a GET request to `/api/generate-dashboard?stockQuery=...`.
*   API route (`route.ts`) executes `run_pipeline.py`.
*   `run_pipeline.py` executes `stonk_research_agent`, then `dashboard_agent`, and prints the TSX string fragment to `stdout`.
*   API route captures the TSX string.
*   API route writes TSX to `/temp/dynamic_....tsx`.
*   API route writes basic CSS input to `/temp/input_....css`.
*   API route executes `npx tailwindcss ...` generating `/temp/output_....css`.
*   API route reads `/temp/output_....css`.
*   API route cleans up temporary files.
*   API route returns JSON `{ tsx: "...", css: "..." }` to the frontend.
*   Frontend (`page.tsx`) receives the JSON.
*   Frontend compiles the `tsx` string using Babel Standalone.
*   Frontend injects the `css` string into a `<style>` tag in the `<head>`.
*   Frontend renders the compiled React element.

## NextChat Integration (New Primary UI)

*   **Primary Interface:** The project will now use `NextChat` (cloned at `/Users/jannoszczyk/Documents/Github/slow-takeoff/nextchat/`) as the main user interface.
*   **MCP Server Management:** NextChat is responsible for managing the lifecycle (spawning, monitoring) of MCP servers. This is configured via `nextchat/app/mcp/mcp_config.json`.
    *   Each server is defined with a `command`, `args` (arguments to start the server script), and optional `env` variables.
    *   The `ENABLE_MCP=true` environment variable in `nextchat/.env.local` activates this functionality.
*   **MCP Communication:** NextChat's internal MCP client (likely in `nextchat/app/mcp/client.ts` and `actions.ts`) will communicate with the configured and spawned MCP servers (e.g., `stonk-research-mcp-server`, `wealthfront-mcp-server`).
*   **UI Component Display:** The mechanism for displaying custom UI components (like TSX from `stonk-research-mcp-server`) within NextChat is still under investigation. It might involve:
    *   NextChat's "Artifacts" feature.
    *   A custom NextChat plugin.
    *   Direct rendering capabilities if a tool response is identified as rich content.
*   **Original Dashboard (`dashboard/`):** The existing Next.js dashboard in the `dashboard/` directory might become a secondary tool or its UI/API patterns might be adapted for NextChat plugins/artifacts if direct TSX rendering in NextChat proves complex.

```mermaid
graph LR
    User --> NC[NextChat UI];
    NC -->|Loads Config| NCC(nextchat/app/mcp/mcp_config.json);
    NC -->|Spawns & Manages| SRS(stonk-research-mcp-server);
    NC -->|Spawns & Manages| WFS(wealthfront-mcp-server);
    NC -->|MCP Call: research_stock_or_company| SRS;
    SRS -->|Executes| RPP(run_pipeline.py);
    RPP -->|Generates TSX String| SRS;
    SRS -->|Returns TSX String| NC;
    NC -->|MCP Call: get_assets etc.| WFS;
    WFS -->|Returns Data| NC;
    NC -->|Renders Output (TSX via Artifacts/Plugin?)| User;
```

*(This file documents the system's structure and technical design, referencing projectbrief.md.)*
