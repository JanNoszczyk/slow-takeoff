from dashboard_agent import generate_dashboard

try:
    from openai import Tool
except ImportError:
    raise ImportError("openai-agents SDK is required. Install with: pip install openai")

dashboard_tool = Tool.from_function(
    function=generate_dashboard,
    name="generate_dashboard",
    description="Builds the dashboard as defined in the 'dashboard' project folder and returns the build status and output path.",
)

# Example: Register this tool with your agent
# tools = [dashboard_tool]
# agent = OpenAIAgent(tools=tools, ...)
