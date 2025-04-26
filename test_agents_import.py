try:
    from agents import Agent, Runner, WebSearchTool
    from agents.tools.errors import UserError
    print("SUCCESS: agents package imported.")
except Exception as e:
    print("FAILURE:", e)
