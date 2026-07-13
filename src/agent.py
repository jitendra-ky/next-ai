"""
Agent definition exposed for LangGraph Studio.

Studio looks for a variable (here: `agent`) that is a compiled
LangGraph graph or an object created by create_agent(). It does NOT
run this file directly with python — it's imported by `langgraph dev`.
"""

from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_groq import ChatGroq

from src.aqi_tools import CAAQMS_TOOLS


@tool
def calculator(expression: str) -> str:
    """Evaluates a basic math expression, e.g. '12 * 7 + 3'."""
    try:
        return str(eval(expression))
    except Exception as e:
        return f"Error: {e}"


# llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash")
llm = ChatGroq(model="llama-3.3-70b-versatile")
agent = create_agent(
    model=llm,
    tools=[calculator] + CAAQMS_TOOLS,
)
