import os
import sys
import json
from pathlib import Path

import certifi
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_groq import ChatGroq


# ==========================================
# Environment configuration
# ==========================================

load_dotenv()

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
AVIATION_STACK_API_KEY = os.getenv("AVIATIONSTACK_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


# Automatically find the current project folder.
PROJECT_DIR = Path(__file__).resolve().parent
WEATHER_SERVER_PATH = PROJECT_DIR / "weather_mcp.py"


# Preserve the complete Windows environment
# when starting local stdio MCP servers.
AVIATION_ENV = os.environ.copy()
AVIATION_ENV["AVIATION_STACK_API_KEY"] = (
    AVIATION_STACK_API_KEY or ""
)

WEATHER_ENV = os.environ.copy()
WEATHER_ENV["OPENWEATHER_API_KEY"] = (
    OPENWEATHER_API_KEY or ""
)


# ==========================================
# LLM
# ==========================================

llm = ChatGroq(
    model="openai/gpt-oss-20b",
    api_key=GROQ_API_KEY
)


# ==========================================
# MCP client configuration
# ==========================================

client = MultiServerMCPClient(
    {
        "tavily": {
            "transport": "streamable_http",
            "url": (
                "https://mcp.tavily.com/mcp/"
                f"?tavilyApiKey={TAVILY_API_KEY}"
            )
        },

        "aviationstack": {
            "transport": "stdio",
            "command": "uvx",
            "args": [
                "aviationstack-mcp"
            ],
            "env": AVIATION_ENV
        },

        "weather": {
            "transport": "stdio",

            # Use the same Python environment
            # that runs app.py.
            "command": sys.executable,

            # Automatically use weather_mcp.py
            # from the current project directory.
            "args": [
                str(WEATHER_SERVER_PATH)
            ],

            "env": WEATHER_ENV
        }
    }
)


# ==========================================
# Diagnostic function
# ==========================================

async def get_all_tools():
    """
    Load each MCP server separately.

    A broken server will not prevent the other
    working servers from loading.
    """

    all_tools = []

    for server_name in (
        "tavily",
        "aviationstack",
        "weather"
    ):

        try:

            tools = await client.get_tools(
                server_name=server_name
            )

            all_tools.extend(tools)

            print(
                f"\nAvailable tools from "
                f"{server_name} MCP:\n"
            )

            for tool in tools:
                print(tool.name)

        except Exception as error:

            print(
                f"\nCould not connect to "
                f"{server_name} MCP:\n{error}\n"
            )

    return all_tools


# ==========================================
# Tavily MCP tool
# ==========================================

search_tool = None


async def initialize_mcp():
    """
    Initialize only Tavily.

    AviationStack and Weather are initialized
    independently.
    """

    global search_tool

    if search_tool is not None:
        return

    tools = await client.get_tools(
        server_name="tavily"
    )

    tools_by_name = {
        tool.name: tool
        for tool in tools
    }

    search_tool = tools_by_name.get(
        "tavily_search"
    )

    if search_tool is None:

        available_tools = ", ".join(
            tools_by_name.keys()
        )

        raise RuntimeError(
            "Tavily MCP connected, but the "
            "'tavily_search' tool was not found. "
            f"Available tools: "
            f"{available_tools or 'none'}"
        )


def _clean_tavily_result(result) -> str:
    """
    Convert the raw Tavily MCP response into
    clean text that can be displayed by the
    frontend and passed to the itinerary agent.
    """

    if not result:
        return "No hotel search results found."

    try:

        # --------------------------------------
        # Case 1: MCP returns a list
        # --------------------------------------

        if isinstance(result, list):

            for item in result:

                if not isinstance(item, dict):
                    continue

                text = item.get("text")

                if not text:
                    continue

                # Tavily JSON is usually stored
                # inside the MCP text field.
                try:

                    tavily_data = json.loads(text)

                except json.JSONDecodeError:

                    return str(text)

                results = tavily_data.get(
                    "results",
                    []
                )

                if not results:

                    answer = tavily_data.get(
                        "answer"
                    )

                    if answer:
                        return str(answer)

                    return (
                        "No relevant hotel results "
                        "were found."
                    )

                cleaned_results = []

                for index, search_result in enumerate(
                    results[:5],
                    start=1
                ):

                    title = search_result.get(
                        "title",
                        "Untitled result"
                    )

                    url = search_result.get(
                        "url",
                        ""
                    )

                    content = search_result.get(
                        "content",
                        ""
                    )

                    content = str(
                        content
                    ).strip()

                    # Avoid dumping extremely
                    # large search-result content.
                    if len(content) > 700:

                        content = (
                            content[:700]
                            .rstrip()
                            + "..."
                        )

                    formatted_result = (
                        f"### {index}. {title}\n\n"
                        f"Source: {url}\n\n"
                        f"{content}"
                    )

                    cleaned_results.append(
                        formatted_result
                    )

                return "\n\n".join(
                    cleaned_results
                )

        # --------------------------------------
        # Case 2: MCP directly returns a dict
        # --------------------------------------

        if isinstance(result, dict):

            results = result.get(
                "results",
                []
            )

            if results:

                cleaned_results = []

                for index, search_result in enumerate(
                    results[:5],
                    start=1
                ):

                    title = search_result.get(
                        "title",
                        "Untitled result"
                    )

                    url = search_result.get(
                        "url",
                        ""
                    )

                    content = search_result.get(
                        "content",
                        ""
                    )

                    content = str(
                        content
                    ).strip()

                    if len(content) > 700:

                        content = (
                            content[:700]
                            .rstrip()
                            + "..."
                        )

                    cleaned_results.append(
                        (
                            f"### {index}. {title}\n\n"
                            f"Source: {url}\n\n"
                            f"{content}"
                        )
                    )

                return "\n\n".join(
                    cleaned_results
                )

            answer = result.get(
                "answer"
            )

            if answer:
                return str(answer)

        # --------------------------------------
        # Final fallback
        # --------------------------------------

        return str(result)

    except Exception as exc:

        print(
            "TAVILY RESULT PARSING ERROR:",
            type(exc).__name__,
            exc,
            flush=True
        )

        return str(result)


async def tavily_mcp_search(query: str):

    await initialize_mcp()

    result = await search_tool.ainvoke(
        {
            "query": query
        }
    )

    # Convert raw MCP/Tavily output
    # into clean readable hotel information.
    return _clean_tavily_result(result)


# ==========================================
# AviationStack MCP tools
# ==========================================

aviation_tools = {}


async def initialize_aviation_tools():

    global aviation_tools

    if aviation_tools:
        return

    # Load only AviationStack.
    tools = await client.get_tools(
        server_name="aviationstack"
    )

    aviation_tools = {
        tool.name: tool
        for tool in tools
    }

    if not aviation_tools:

        raise RuntimeError(
            "AviationStack MCP connected but "
            "returned no tools."
        )


async def aviation_mcp_call(
    tool_name: str,
    tool_args: dict = None
):

    await initialize_aviation_tools()

    tool = aviation_tools.get(
        tool_name
    )

    if tool is None:

        available_tools = ", ".join(
            sorted(
                aviation_tools.keys()
            )
        )

        raise ValueError(
            f"AviationStack tool '{tool_name}' "
            "was not found. "
            f"Available tools: "
            f"{available_tools or 'none'}"
        )

    result = await tool.ainvoke(
        tool_args or {}
    )

    return result


# ==========================================
# Weather MCP tools
# ==========================================

weather_tool = None
forecast_tool = None


async def initialize_weather_tools():

    global weather_tool
    global forecast_tool

    if (
        weather_tool is not None
        and forecast_tool is not None
    ):
        return

    if not WEATHER_SERVER_PATH.exists():

        raise FileNotFoundError(
            "Weather MCP server file was not found: "
            f"{WEATHER_SERVER_PATH}"
        )

    # Load only Weather.
    tools = await client.get_tools(
        server_name="weather"
    )

    tools_by_name = {
        tool.name: tool
        for tool in tools
    }

    weather_tool = tools_by_name.get(
        "get_current_weather"
    )

    forecast_tool = tools_by_name.get(
        "get_forecast"
    )

    missing_tools = []

    if weather_tool is None:

        missing_tools.append(
            "get_current_weather"
        )

    if forecast_tool is None:

        missing_tools.append(
            "get_forecast"
        )

    if missing_tools:

        available_tools = ", ".join(
            tools_by_name.keys()
        )

        raise RuntimeError(
            "Missing Weather MCP tools: "
            f"{', '.join(missing_tools)}. "
            f"Available tools: "
            f"{available_tools or 'none'}"
        )


async def weather_mcp_search(city: str):

    await initialize_weather_tools()

    result = await weather_tool.ainvoke(
        {
            "city": city
        }
    )

    return result


async def forecast_mcp_search(city: str):

    await initialize_weather_tools()

    result = await forecast_tool.ainvoke(
        {
            "city": city
        }
    )

    return result


# ==========================================
# Destination extractor
# ==========================================

def extract_destination(query: str):

    prompt = f"""
Extract only the destination city or country.

Query:
{query}

Return only destination name.
"""

    response = llm.invoke(
        prompt
    )

    return response.content.strip()