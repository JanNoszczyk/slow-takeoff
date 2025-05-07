# Project Progress

## Current Status

*   **State:** Shifted to using NextChat as the primary UI. Implemented TSX rendering within NextChat using its Artifacts system. This involves dynamic Tailwind CSS generation via a new API route and client-side logic to prepare and display HTML artifacts.
*   **Milestones:**
    *   Successfully debugged initial pipeline execution errors (previous milestone).
    *   Successfully refactored the architecture to incorporate dynamic TSX generation (initial version for original dashboard - previous milestone).
    *   Implemented (but did not fully test) browser-side compilation and iframe approaches (previous milestone).
    *   Implemented the "Dynamic Tailwind Build" approach in code for original dashboard (previous milestone).
    *   **New:** Cloned and configured NextChat for MCP server integration.
    *   **New:** Created `nextchat/app/api/generate-tailwind-css/route.ts` for dynamic CSS generation.
    *   **New:** Modified `nextchat/app/store/chat.ts` to handle `stonk-research-mcp-server` responses, prepare HTML artifacts (including TSX, React/Babel CDN, and dynamic Tailwind CSS), and post to NextChat's `/api/artifacts`.
    *   **New:** Modified `nextchat/app/components/chat.tsx` to detect artifact messages, fetch artifact content, and render it using `HTMLPreview`.

## What Works (Presumed)

*   **`stonk_research_agent`:** Gathers research data and produces JSON (unchanged).
*   **`project_agents/dashboard_agent`:** Generates TSX code string for news boxes (unchanged, TSX now consumed by NextChat flow).
*   **`run_pipeline.py`:** Orchestrates agent calls and outputs the TSX string (unchanged, TSX now consumed by NextChat flow).
*   **NextChat MCP Configuration:** `nextchat/app/mcp/mcp_config.json` is set up to spawn MCP servers.
*   **Dynamic Tailwind CSS API Route:** `nextchat/app/api/generate-tailwind-css/route.ts` is implemented.
*   **Client-Side Artifact Preparation:** Logic in `nextchat/app/store/chat.ts` to create HTML artifacts is implemented.
*   **Client-Side Artifact Rendering:** Logic in `nextchat/app/components/chat.tsx` to display HTML artifacts using `HTMLPreview` is implemented.

## What's Left to Build / Verify

*   **Test End-to-End TSX Rendering in NextChat:** The entire new workflow needs to be tested:
    *   Calling `stonk-research-mcp-server` from NextChat.
    *   Dynamic Tailwind CSS generation.
    *   Artifact creation and storage.
    *   Inline rendering of the artifact in `HTMLPreview` within a chat message.
    *   Correct application of Tailwind styles inside the iframe.
*   **Verify General NextChat MCP Integration:** Test communication with all configured MCP servers.
*   **Performance of Dynamic Tailwind CSS:** Assess the speed of the `/api/generate-tailwind-css` route.
*   **Error Handling:** Review and improve error handling throughout the new TSX rendering pipeline in NextChat.
*   **Security of `HTMLPreview`:** Confirm sandboxing is adequate.
*   **Artifact API Payload:** Ensure the payload sent to `/api/artifacts` from `chat.ts` matches the API's expectations.
*   **Define Full Scope:** `projectbrief.md` and `productContext.md` are still undefined.
*   **Original Dashboard (`dashboard/`) Status:** Decide if it's deprecated or if parts will be reused.

## Known Issues & Bugs

*   **Styling Failure (Original Dashboard):** Tailwind CSS styles were not applied when rendering agent-generated TSX via `dangerouslySetInnerHTML` in the original `dashboard/` app. (This issue is what the new NextChat approach aims to solve differently).
*   **Performance Concern (New API Route):** The new `/api/generate-tailwind-css` route in NextChat, like the previous approach in the original dashboard, involves runtime CLI execution and could be a performance bottleneck.
*   **Complexity (New Workflow):** While potentially more robust, the new workflow involving artifact creation, client-side fetching for preview, and iframe rendering still has multiple moving parts.

*(This file provides a snapshot of the project's completion status, informed by activeContext.md.)*
