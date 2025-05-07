# Active Context

## Current Focus

*   **Integrating NextChat as Primary UI:** Shifting focus from the original `dashboard/` to using `NextChat` (cloned at `/Users/jannoszczyk/Documents/Github/slow-takeoff/nextchat/`) as the main user interface.
*   **MCP Server Integration with NextChat:** Configuring NextChat to manage and communicate with existing MCP servers (`stonk-research-mcp-server`, `wealthfront-mcp-server`) via `nextchat/app/mcp/mcp_config.json`.
*   **TSX Rendering in NextChat via Artifacts:** Implemented the chosen approach for rendering TSX from `stonk-research-mcp-server` within NextChat using its Artifacts system and dynamic Tailwind CSS generation.

## Recent Changes & Decisions

*   **New UI Direction:** Decided to use `NextChat` as the primary chat interface, leveraging its MCP support.
*   **Cloned NextChat:** Cloned `ChatGPTNextWeb/NextChat` repository into `/Users/jannoszczyk/Documents/Github/slow-takeoff/nextchat/`.
*   **Initial NextChat Setup:** Installed dependencies (`yarn install`) and created `nextchat/.env.local` with `ENABLE_MCP=true` (OpenAI API key needs to be manually added by user).
*   **Discovered NextChat MCP Configuration:** Found that NextChat manages MCP servers via `nextchat/app/mcp/mcp_config.json`, where each server is defined by a `command`, `args`, and optional `env`.
*   **Created `mcp_config.json`:** Added configurations for `stonk-research-mcp-server` and `wealthfront-mcp-server` in `nextchat/app/mcp/mcp_config.json`.
*   **Previous "Dynamic Tailwind Build" for `dashboard/` is now secondary:** The focus has shifted to NextChat. The complex Tailwind build for the original dashboard is less critical.
*   **Created API for Tailwind CSS:** Implemented `nextchat/app/api/generate-tailwind-css/route.ts` to dynamically generate CSS for TSX strings.
*   **Modified `chat.ts`:** Updated `nextchat/app/store/chat.ts` to intercept `stonk-research-mcp-server`'s `research_stock_or_company` tool responses. This logic now prepares a full HTML document (including React/Babel CDN links, the TSX string, and dynamically generated Tailwind CSS via the new API route) and POSTs it to NextChat's `/api/artifacts` endpoint. The chat message is updated with a special format `[artifact:id]`.
*   **Modified `chat.tsx`:** Updated `nextchat/app/components/chat.tsx` to detect messages with the `[artifact:id]` format. It now fetches the artifact content by ID and renders it using the `HTMLPreview` component for an inline preview of the TSX content.

## Next Steps

1.  **Test End-to-End TSX Rendering Workflow:**
    *   Run NextChat (`cd nextchat && yarn dev`).
    *   Ensure MCP servers (especially `stonk-research-mcp-server`) are running and configured correctly in `nextchat/app/mcp/mcp_config.json`.
    *   Call the `research_stock_or_company` tool from `stonk-research-mcp-server` via the NextChat UI.
    *   Verify:
        *   The `/api/generate-tailwind-css` route is called and returns CSS.
        *   An artifact is created via `/api/artifacts`.
        *   The chat message in NextChat displays the `HTMLPreview` of the rendered TSX.
        *   Tailwind styles are correctly applied within the `HTMLPreview` iframe.
2.  **Verify NextChat MCP Integration (General):**
    *   Ensure user has added their OpenAI API key to `nextchat/.env.local`.
    *   Ensure all necessary environment variables for the MCP servers are correctly sourced.
    *   Test if NextChat successfully spawns and connects to all configured MCP servers.
    *   Attempt to call tools from other MCP servers (e.g., `wealthfront-mcp-server`) to ensure general MCP functionality is intact.
3.  **Refine Artifact Display:**
    *   Review the appearance and usability of the embedded `HTMLPreview`. Adjust default height or styling as needed.
    *   Consider if the link text (e.g., "View Report: ...") above the preview is optimal or if it should be integrated differently.
4.  **Update .clinerules:** Add learnings about the implemented TSX rendering workflow and NextChat integration.
5.  **Address `projectbrief.md` and `productContext.md`:** These core Memory Bank files are still largely undefined and need to be filled out based on the project's goals.

## Open Questions & Considerations

*   **Performance of Dynamic Tailwind CSS:** The `/api/generate-tailwind-css` route involves file I/O and CLI execution, which could be slow. This needs to be tested.
*   **Error Handling:** Review and enhance error handling in the new API route, `chat.ts` artifact preparation, and `chat.tsx` preview rendering.
*   **Security of `HTMLPreview`:** Ensure the sandboxing of the `iframe` in `HTMLPreview` is sufficient for rendering potentially complex, dynamically generated HTML/JS.
*   **Artifact API Payload:** The payload sent to `/api/artifacts` in `chat.ts` (`{ content: htmlToRender, type: "text/html", filename: ... }`) needs to exactly match what `nextchat/app/api/artifacts/route.ts` expects. This was assumed based on common patterns but should be verified against the actual API implementation.
*   **State of Original `dashboard/`:** Is it now deprecated, or will parts be reused? This is still an open question.
*   **NextChat Plugin System:** Further investigation into custom plugins might still be beneficial for more deeply integrated UI experiences, but the current Artifacts-based approach addresses the immediate TSX rendering goal.

*(This file tracks the immediate state of work, building upon productContext.md, systemPatterns.md, and techContext.md.)*
