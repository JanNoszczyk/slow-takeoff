from stonk_research_agent.agent import main

import asyncio

if __name__ == "__main__":
    query = "Research NVIDIA (NVDA), include company overview, recent news, and current stock price."
    asyncio.run(main(query))
