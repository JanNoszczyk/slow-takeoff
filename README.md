# Slow Takeoff: AI-Powered Financial Research Platform

A financial research and portfolio analysis platform that integrates stock research capabilities with WealthArc portfolio data through Model Context Protocol (MCP) servers and NextChat.

## Overview

This project provides AI-powered financial research and portfolio analysis by leveraging:
-   **MCP Servers:** Custom servers for stock research (generating interactive TSX visualizations) and WealthArc API integration (accessing portfolio data).
-   **NextChat:** A chat-based user interface for interacting with the MCP servers.
-   **Dashboard UI:** An alternative UI for visualizing stock research.

The system uses the Model Context Protocol (MCP) to enable AI models to access external tools and data sources, creating a powerful and extensible financial analysis platform.

## Table of Contents

- [Slow Takeoff: AI-Powered Financial Research Platform](#slow-takeoff-ai-powered-financial-research-platform)
  - [Overview](#overview)
  - [Table of Contents](#table-of-contents)
  - [Getting Started](#getting-started)
    - [Prerequisites](#prerequisites)
    - [Installation](#installation)
    - [API Key Configuration](#api-key-configuration)
  - [Running the Application](#running-the-application)
    - [Starting NextChat (Primary UI)](#starting-nextchat-primary-ui)
    - [Running the Dashboard UI (Alternative)](#running-the-dashboard-ui-alternative)
    - [Running MCP Servers or Python Scripts Independently](#running-mcp-servers-or-python-scripts-independently)
  - [Usage Examples](#usage-examples)
  - [Key Features \& Components](#key-features--components)
    - [MCP Servers](#mcp-servers)
    - [User Interfaces](#user-interfaces)
    - [TSX Artifacts](#tsx-artifacts)
  - [Technical Deep Dive](#technical-deep-dive)
    - [Core Architecture](#core-architecture)
    - [Dynamic Tailwind CSS Generation](#dynamic-tailwind-css-generation)
    - [Client-Side TSX Compilation](#client-side-tsx-compilation)
    - [Key Files and Their Roles](#key-files-and-their-roles)
  - [Development with Cline and Memory Bank](#development-with-cline-and-memory-bank)
    - [Cline's Memory Bank](#clines-memory-bank)
    - [Recommended Coding Agent Setup (Cline)](#recommended-coding-agent-setup-cline)
  - [Troubleshooting](#troubleshooting)

## Getting Started

Follow these steps to get the project up and running on your local machine.

### Prerequisites

Before you begin, ensure you have the following installed:
-   **Python:** Version 3.10 or higher.
-   **Node.js:** Version 18.0 or higher.
-   **Yarn:** For managing NextChat dependencies. Install via `npm install -g yarn`.
-   **Git:** For cloning the repository.

You will also need the following API keys:
-   **OpenAI API Key:** Required for the core AI functionalities of NextChat and the stock research agent.
-   **WealthArc API Key:** Required for the WealthArc MCP server to access portfolio data.
-   *(Optional but Recommended)* Additional keys for the stock research agent (Finnhub, AlphaVantage, etc.) for comprehensive data. These are configured in `nextchat/app/mcp/mcp_config.json` for the `stonk_research_mcp_server`.

### Installation

1.  **Clone the Repository:**
    ```bash
    git clone <repository_url> slow-takeoff
    cd slow-takeoff
    ```

2.  **Set up Python Environment:**
    It's recommended to use a virtual environment:
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows, use: .venv\Scripts\activate
    pip install -r requirements.txt
    ```

3.  **Set up NextChat:**
    This project uses a customized version of NextChat. A setup script is provided to clone the correct version of NextChat and apply local modifications:
    ```bash
    chmod +x setup-nextchat.sh
    ./setup-nextchat.sh
    ```
    This script will:
    -   Clone NextChat into the `nextchat/` directory.
    -   Checkout the specific commit (`3fdbf01098dd86aec5f5644532de222e87ba7e50`) our modifications are based on.
    -   Copy custom files from `custom-nextchat-files/` into the `nextchat/` directory.
    -   Create a basic `nextchat/.env.local`.

    For more details on the NextChat setup and custom files, see [README-nextchat.md](./README-nextchat.md).

4.  **Install NextChat Dependencies:**
    ```bash
    cd nextchat
    yarn install
    cd .. 
    ```

### API Key Configuration

**IMPORTANT:** You must configure your API keys for the application to function correctly.

1.  **NextChat OpenAI API Key:**
    -   Edit `nextchat/.env.local`.
    -   Add your OpenAI API key:
        ```
        OPENAI_API_KEY=your_openai_api_key_here
        ENABLE_MCP=true 
        ```
        (Ensure `ENABLE_MCP=true` is present).

2.  **MCP Server API Keys (within NextChat context):**
    -   The MCP servers, when launched by NextChat, get their API keys from `nextchat/app/mcp/mcp_config.json`.
    -   **CRITICAL:** The `nextchat/app/mcp/mcp_config.json` file in this repository contains **placeholder API keys**. You **MUST** replace these with your actual API keys.
    -   Edit `nextchat/app/mcp/mcp_config.json` and update the `env` sections for `stonk_research_mcp_server` and `wealthfront_mcp_server` with your keys.
        ```json
        // Example for stonk_research_mcp_server in nextchat/app/mcp/mcp_config.json
        "stonk_research_mcp_server": {
          // ... other config ...
          "env": {
            "NODE_ENV": "development",
            "OPENAI_API_KEY": "YOUR_OPENAI_KEY", // Replace this
            "FINNHUB_API_KEY": "YOUR_FINNHUB_KEY", // Replace this
            // ... other keys ...
          },
          // ...
        },
        // Example for wealthfront_mcp_server
        "wealthfront_mcp_server": {
            // ... other config ...
            "env": {
                "NODE_ENV": "development",
                "WEALTH_ARC_API_KEY": "YOUR_WEALTHARC_KEY", // Replace this
                "VIDAR_BASE_URL": "https://api.wealthdatabox.com/v1/"
            },
            // ...
        }
        ```

3.  **API Keys for Standalone Script/Server Execution:**
    -   If you plan to run Python scripts (e.g., `run_pipeline.py`) or MCP servers independently (outside of NextChat's management), you'll need to set environment variables directly in your terminal or via a `.env` file in the project root (this project is configured to load `.env` files for Python scripts).
        ```bash
        # Example for project root .env file
        OPENAI_API_KEY=your_openai_api_key_here
        FINNHUB_API_KEY=your_finnhub_api_key_here
        # ... other keys ...
        ```

## Running the Application

This section explains how to run the different parts of the Slow Takeoff platform. The primary way to interact with the system is through the NextChat interface, which manages the MCP servers.

### Starting NextChat (Primary UI)

NextChat serves as the main user interface and orchestrator for the MCP servers.

1.  **Prerequisites Check:** Ensure you have completed all steps in the [Getting Started](#getting-started) section, especially:
    *   Cloned the repository and run `./setup-nextchat.sh`.
    *   Installed dependencies (`pip install -r requirements.txt` and `cd nextchat && yarn install`).
    *   **Crucially, configured your API keys** in `nextchat/.env.local` (for `OPENAI_API_KEY`) and replaced **all placeholder keys** in `nextchat/app/mcp/mcp_config.json` with your actual keys.
    *   **Important for other developers:** The paths to the MCP server executables within `nextchat/app/mcp/mcp_config.json` (e.g., `/Users/jannoszczyk/Documents/Cline/MCP/...`) are specific to the original development environment. **You will likely need to update these paths** to point to where your MCP server builds are located if you are not the original developer or if you have them in different locations.

2.  **Start NextChat:**
    ```bash
    cd nextchat
    yarn dev
    ```

3.  **Access NextChat:**
    Open your browser and navigate to `http://localhost:3000` (or the port NextChat indicates it's running on).

    NextChat will attempt to start and manage the MCP servers (Stock Research and WealthArc) as defined in `nextchat/app/mcp/mcp_config.json`. You should see logs in the terminal where you ran `yarn dev` indicating the status of these MCP servers.

### Running the Dashboard UI (Alternative)

The `dashboard/` directory contains an alternative, standalone UI. TSX artifact rendering is generally more stable in this UI.

1.  **API Key Setup:** If the dashboard's API route (`dashboard/src/app/api/generate-dashboard/route.ts`) relies on API keys for executing Python scripts, ensure these are available in its environment (e.g., via a `.env` file in the project root, which Python scripts can load).
2.  **Start the Dashboard:**
    ```bash
    cd dashboard
    npm install # If you haven't already
    npm run dev
    ```
3.  **Access Dashboard:**
    Open your browser to the port specified (e.g., `http://localhost:3001`).

### Running MCP Servers or Python Scripts Independently

For development, debugging, or testing individual components, you can run them outside of NextChat's management.

1.  **Python Scripts (e.g., `run_pipeline.py` for stock research):**
    -   Activate your Python virtual environment: `source .venv/bin/activate` (or `.venv\Scripts\activate` on Windows).
    -   Ensure required API keys (e.g., `OPENAI_API_KEY`, `FINNHUB_API_KEY`) are set as environment variables or defined in a `.env` file in the project root.
    -   Example:
        ```bash
        python run_pipeline.py "MSFT"
        ```

2.  **MCP Servers (Standalone):**
    This is useful if you want to test an MCP server directly or if NextChat is having trouble managing them.
    -   **Stock Research MCP Server:**
        -   Set necessary environment variables (e.g., `OPENAI_API_KEY`, `FINNHUB_API_KEY`).
        -   Run the server:
            ```bash
            node /path/to/your/stonk-research-mcp-server/build/index.js 
            ```
            *(Adjust the path to your actual server location.)*
    -   **WealthArc MCP Server:**
        -   Set necessary environment variables (e.g., `WEALTH_ARC_API_KEY`).
        -   Run the server:
            ```bash
            node /path/to/your/wealthfront-mcp-server/build/index.js
            ```
            *(Adjust the path to your actual server location.)*

    When running MCP servers standalone, NextChat will not attempt to manage them if they are already running on the expected ports (though NextChat's primary design is to spawn them).

## Usage Examples

Once NextChat is running and configured:

-   **Researching a Stock:**
    In the NextChat interface, type a query like:
    `Research Apple stock and show me recent news`
    NextChat will use the `stonk_research_mcp_server`. The TSX artifact rendering in NextChat is experimental; you might see a link to an HTML artifact or a direct (but potentially unstyled) preview.

-   **Accessing Portfolio Data:**
    Type a query like:
    `Show me my portfolio assets`
    NextChat will use the `wealthfront_mcp_server`. Results are typically textual.

For a more stable TSX visualization experience, use the **Dashboard UI**.

## Key Features & Components

### MCP Servers

-   **Stock Research MCP Server (`stonk_research_mcp_server`):**
    -   Performs comprehensive stock research using various data sources.
    -   Generates interactive TSX visualizations for displaying results.
    -   Key tool: `research_stock_or_company`.
-   **WealthArc MCP Server (`wealthfront_mcp_server`):**
    -   Connects to the WealthArc API.
    -   Provides tools to fetch portfolio assets, positions, transactions, and metrics (e.g., `get_assets`, `get_portfolios`).

### User Interfaces

-   **NextChat (`nextchat/`):**
    -   The primary, chat-based UI.
    -   Manages and interacts with MCP servers.
    -   Experimental support for rendering TSX artifacts from the stock research server.
    -   Custom modifications are managed via `custom-nextchat-files/` and `setup-nextchat.sh`. See [README-nextchat.md](./README-nextchat.md) for details.
-   **Dashboard UI (`dashboard/`):**
    -   A standalone Next.js application.
    -   Features a more robust implementation of TSX artifact rendering with dynamic Tailwind CSS.

### TSX Artifacts

-   Dynamically generated TypeScript React (TSX) code snippets.
-   Created by the stock research agent to visualize financial data (charts, news summaries, etc.).
-   Rendered client-side after compilation with Babel.

## Technical Deep Dive

This section provides more insight into the project's architecture.

### Core Architecture

The system generally follows this flow when using NextChat:
```mermaid
graph LR
    User --> NC[NextChat UI];
    NC -->|Loads Config| NCC(nextchat/app/mcp/mcp_config.json);
    NC -->|Spawns & Manages| SRS(stonk_research_mcp_server);
    NC -->|Spawns & Manages| WFS(wealthfront_mcp_server);
    NC -->|MCP Call: research_stock_or_company| SRS;
    SRS -->|Executes Python Pipeline| RPP(run_pipeline.py);
    RPP -->|Generates TSX String| SRS;
    SRS -->|Returns TSX String| NC;
    NC -->|MCP Call: get_assets etc.| WFS;
    WFS -->|Returns Data| NC;
    NC -->|Renders Output (Text or Artifact)| User;
```

### Dynamic Tailwind CSS Generation

To style runtime-generated TSX components:
-   **Dashboard UI:** An API route saves the TSX, runs `npx tailwindcss` CLI, and returns TSX + CSS.
-   **NextChat (Experimental):** A dedicated API route (`/api/generate-tailwind-css`) generates CSS for TSX strings, which is then included in HTML artifacts.

### Client-Side TSX Compilation

-   Both UIs use Babel Standalone (loaded via CDN) to compile TSX strings into executable JavaScript/React elements at runtime in the browser.

### Key Files and Their Roles

-   **`setup-nextchat.sh`**: Script to initialize the `nextchat/` directory with the correct upstream version and custom patches.
-   **`custom-nextchat-files/`**: Contains the modified files for NextChat.
-   **`README-nextchat.md`**: Detailed information about the NextChat setup and customization.
-   **`nextchat/app/mcp/mcp_config.json`**: Defines MCP servers for NextChat to manage. **(Contains placeholder API keys - MUST BE EDITED)**
-   **`nextchat/app/store/chat.ts`**: Core NextChat logic, modified for artifact handling.
-   **`nextchat/app/components/chat.tsx`**: NextChat UI component, modified for artifact display.
-   **`nextchat/app/api/generate-tailwind-css/route.ts`**: API for dynamic Tailwind CSS in NextChat.
-   **`dashboard/src/app/api/generate-dashboard/route.ts`**: Dashboard API for pipeline execution and TSX/CSS generation.
-   **`dashboard/src/app/page.tsx`**: Main UI for the dashboard.
-   **`run_pipeline.py`**: Orchestrates backend Python agents for stock research.
-   **`stonk_research_agent/` & `project_agents/dashboard_agent/`**: Python agent code.
-   **`memory-bank/`**: Contains documentation for Cline's Memory Bank (see below).

## Development with Cline and Memory Bank

This project was developed with the assistance of Cline, an AI coding agent. To maintain context and ensure efficient development across sessions, Cline utilizes a "Memory Bank".

### Cline's Memory Bank

Cline's Memory Bank is a structured documentation system that helps Cline (and human developers) understand the project's context, goals, and current state. It's crucial for Cline because its memory resets between sessions.

**Purpose:**
The Memory Bank serves as Cline's long-term memory, enabling it to:
-   Quickly get up to speed on the project.
-   Understand complex architectures and design decisions.
-   Track progress and identify next steps.
-   Maintain consistency in coding style and patterns.

**Structure:**
The Memory Bank consists of several core Markdown files (like `projectbrief.md`, `activeContext.md`, `systemPatterns.md`, etc.) that build upon each other to provide a comprehensive overview of the project. You can find these files in the `memory-bank/` directory.

For a detailed explanation of the Memory Bank concept and its structure, please refer to the [official Cline Memory Bank documentation](https://github.com/nickbaumann98/cline_docs/blob/main/prompting/custom%20instructions%20library/cline-memory-bank.md).

### Recommended Coding Agent Setup (Cline)

Using a coding agent like Cline can significantly accelerate development. Here's a recommended setup, particularly effective with powerful models like Gemini 2.5 Pro:

1.  **Install VS Code:** Download from [https://code.visualstudio.com/](https://code.visualstudio.com/).
2.  **Install Cline Extension:**
    *   Open VS Code.
    *   Go to the Extensions marketplace (usually an icon on the left sidebar).
    *   Search for "Cline" and install it.
3.  **Configure Cline:**
    *   After installation, a Cline icon (robot head) should appear in the left sidebar. Click it to open Cline.
    *   The default view includes a chat window.
    *   Click the small settings icon (usually at the top of the Cline panel) to open the settings tab.
    *   Here, you can enter your API keys for various AI models.
4.  **Get API Keys (Gemini 2.5 Pro Recommended):**
    *   Cline supports many models, but Gemini 2.5 Pro (or Flash for a cheaper, slightly less capable option) is highly recommended.
    *   **Quick Start (Rate-Limited):** You can get an API key from [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey). However, this key has severe rate limits and is not suitable for extensive coding.
    *   **For Unrestricted Use (Recommended):**
        *   **OpenRouter:**
            *   Go to [https://openrouter.ai/](https://openrouter.ai/).
            *   OpenRouter allows you to use many AI models (including Gemini) with a single API key. Pricing is similar to native model APIs, though it might be slightly slower. It's very easy to set up.
        *   **Google Cloud Platform (GCP) Vertex AI:**
            *   This provides Gemini models directly from Google.
            *   Follow the Cline documentation for setting up Vertex AI: [https://docs.cline.bot/custom-model-configs/gcp-vertex-ai](https://docs.cline.bot/custom-model-configs/gcp-vertex-ai).
            *   When setting up, you can usually skip section 2.2 (enabling models), as Gemini models are often enabled by default. If you plan to use other models like Claude via Vertex AI, you might need to enable them.

By using Cline with a robust model and API key setup, you can leverage AI to assist in coding, debugging, documentation, and more, as was done for this project.

## Troubleshooting

-   **API Key Issues**:
    -   Ensure all required API keys are correctly set.
    -   For NextChat: Check `nextchat/.env.local` (for `OPENAI_API_KEY`) AND `nextchat/app/mcp/mcp_config.json` (for keys used by MCP servers like `FINNHUB_API_KEY`, `WEALTH_ARC_API_KEY`). **Remember to replace placeholders in `mcp_config.json`!**
    -   For standalone scripts: Check environment variables or your root `.env` file.
-   **NextChat MCP Connection**:
    -   Verify `ENABLE_MCP=true` is set in `nextchat/.env.local`.
    -   Check NextChat server logs for errors related to spawning or connecting to MCP servers.
    -   Ensure paths to MCP server executables in `nextchat/app/mcp/mcp_config.json` are correct for your system.
-   **MCP Server Errors**: Check the individual console output/logs of the `stonk-research-mcp-server` or `wealthfront-mcp-server` if they are run independently or if NextChat logs indicate issues with them.
-   **Python Dependencies**: Make sure you are in the correct virtual environment (`source .venv/bin/activate`) and have run `pip install -r requirements.txt`.
-   **Node.js Dependencies**: Ensure `yarn install` (for `nextchat/`) or `npm install` (for `dashboard/`) has been run in the respective directories.
-   **TSX Rendering Issues in NextChat**: This feature is experimental. Inspect the generated HTML artifact (if a link is provided) and browser console logs for errors. Check the NextChat server logs and the `/api/generate-tailwind-css` route's logs.
