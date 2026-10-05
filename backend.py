
import os
import certifi
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------
# SSL configuration
# ---------------------------------------------------------

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()


# ---------------------------------------------------------
# Standard imports
# ---------------------------------------------------------

from typing import Any, TypedDict, Annotated
import operator
import uuid
import asyncio
import json


# ---------------------------------------------------------
# Database
# ---------------------------------------------------------

import psycopg
from psycopg.rows import dict_row


# ---------------------------------------------------------
# LangGraph
# ---------------------------------------------------------

from langgraph.graph import (
    StateGraph,
    START,
    END,
)

from langgraph.checkpoint.postgres import (
    PostgresSaver,
)

from langgraph.types import (
    Command,
    interrupt,
)


# ---------------------------------------------------------
# LangChain
# ---------------------------------------------------------

from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
)

from langchain_groq import ChatGroq


# ---------------------------------------------------------
# MCP helpers
# ---------------------------------------------------------

from mcp_flight import (
    tavily_mcp_search,
    aviation_mcp_call,
    extract_destination,
    forecast_mcp_search,
    weather_mcp_search,
)


# =========================================================
# DATABASE
# =========================================================

def get_database_url():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError(
            "DATABASE_URL is missing. "
            "Please add your Render PostgreSQL External Database URL to .env"
        )

    if "sslmode=" not in database_url:
        separator = "&" if "?" in database_url else "?"
        database_url = (
            f"{database_url}{separator}sslmode=require"
        )

    return database_url


# =========================================================
# GROQ
# =========================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError(
        "GROQ_API_KEY is missing. "
        "Please add it to your .env file."
    )


llm = ChatGroq(
    model="openai/gpt-oss-20b",
    api_key=GROQ_API_KEY,
)


# =========================================================
# STATE
# =========================================================

class TravelState(TypedDict, total=False):

    messages: Annotated[
        list[AnyMessage],
        operator.add
    ]

    user_query: str

    guardrail_allowed: bool
    guardrail_reason: str

    selected_agents: list[str]

    trip_constraints: dict[str, Any]

    supervisor_reasoning: str

    flight_results: str
    hotel_results: str
    weather_results: str
    budget_results: str

    itinerary: str

    approval_request: str

    approved: bool
    human_feedback: str

    final_response: str

    llm_calls: int


# =========================================================
# AGENT CONFIGURATION
# =========================================================

KNOWN_AGENTS = {
    "flight_agent",
    "hotel_agent",
    "weather_agent",
    "budget_agent",
    "itinerary_agent",
}


AGENT_ORDER = [
    "flight_agent",
    "hotel_agent",
    "weather_agent",
    "budget_agent",
    "itinerary_agent",
]


# =========================================================
# HELPERS
# =========================================================

def _llm_text(
    system_prompt: str,
    user_prompt: str,
) -> str:

    response = llm.invoke(
        [
            SystemMessage(
                content=system_prompt
            ),
            HumanMessage(
                content=user_prompt
            ),
        ]
    )

    return str(response.content)


def _json_from_llm(
    text: str,
) -> dict[str, Any]:

    start = text.find("{")
    end = text.rfind("}")

    if (
        start == -1
        or end == -1
        or end < start
    ):
        raise ValueError(
            "The model did not return a JSON object."
        )

    return json.loads(
        text[start:end + 1]
    )


def _empty_constraints():

    return {
        "destination": "",
        "origin": "",
        "duration": "",
        "budget": "",
        "travel_style": "",
        "special_preferences": [],
    }


# =========================================================
# GUARDRAIL
# =========================================================

GUARDRAIL_PROMPT = """
You are the safety and relevance guardrail
for a travel planning application.

Determine whether the user's request is:

1. Related to legitimate travel planning
2. Safe to process
3. Not asking for harmful or clearly unrelated content

Return ONLY JSON:

{
    "allowed": true,
    "reason": "short explanation"
}

or

{
    "allowed": false,
    "reason": "short explanation"
}

User request:
{query}
"""


def guardrail_agent(
    state: TravelState,
):

    query = state["user_query"]

    try:

        prompt = GUARDRAIL_PROMPT.format(
            query=query
        )

        response = _llm_text(
            "You are a strict but practical travel application guardrail.",
            prompt,
        )

        data = _json_from_llm(
            response
        )

        allowed = bool(
            data.get(
                "allowed",
                True
            )
        )

        reason = str(
            data.get(
                "reason",
                ""
            )
        )

    except Exception as exc:

        print(
            "GUARDRAIL ERROR:",
            type(exc).__name__,
            exc,
            flush=True,
        )

        # Fail open for normal travel requests.
        allowed = True
        reason = (
            "Guardrail parser fallback."
        )

    return {
        "guardrail_allowed": allowed,
        "guardrail_reason": reason,
        "messages": [
            AIMessage(
                content="Travel request checked."
            )
        ],
        "llm_calls": (
            state.get("llm_calls", 0) + 1
        ),
    }


# =========================================================
# BLOCKED REQUEST
# =========================================================

def guardrail_blocked_agent(
    state: TravelState,
):

    reason = state.get(
        "guardrail_reason",
        "The request could not be processed."
    )

    return {
        "final_response": (
            "I can help with travel planning, "
            "flights, hotels, weather, budgets, "
            "and itineraries.\n\n"
            f"Request not processed: {reason}"
        ),
        "messages": [
            AIMessage(
                content=(
                    "The request was blocked "
                    "by the travel guardrail."
                )
            )
        ],
    }


# =========================================================
# SUPERVISOR
# =========================================================

SUPERVISOR_PROMPT = """
You are the supervisor of a multi-agent
travel planning system.

Analyze the user's request and decide which
specialist agents are needed.

Available agents:

- flight_agent
- hotel_agent
- weather_agent
- budget_agent
- itinerary_agent

The itinerary_agent must ALWAYS be selected.

Return ONLY valid JSON:

{
    "selected_agents": [
        "flight_agent",
        "hotel_agent",
        "weather_agent",
        "budget_agent",
        "itinerary_agent"
    ],
    "trip_constraints": {
        "destination": "",
        "origin": "",
        "duration": "",
        "budget": "",
        "travel_style": "",
        "special_preferences": []
    },
    "reasoning": "short explanation"
}

Important:

- Extract only information actually provided by the user.
- Do NOT invent travel dates.
- Do NOT invent budget values.
- Do NOT invent destination.
- Do NOT invent origin.
- If something is missing, leave it empty.
- Always include itinerary_agent.

User request:
{query}
"""

def supervisor_agent(
    state: TravelState,
):

    query = state["user_query"]

    try:

        # Use replace() instead of .format()
        # because SUPERVISOR_PROMPT contains JSON
        # curly braces that must not be interpreted
        # as Python format placeholders.
        prompt = SUPERVISOR_PROMPT.replace(
            "{query}",
            query
        )

        response = _llm_text(
            (
                "You are a travel supervisor. "
                "Extract facts conservatively."
            ),
            prompt,
        )

        data = _json_from_llm(
            response
        )

        selected_agents = data.get(
            "selected_agents",
            []
        )

        if not isinstance(
            selected_agents,
            list
        ):
            selected_agents = []

        selected_agents = [
            agent
            for agent in selected_agents
            if agent in KNOWN_AGENTS
        ]

        if "itinerary_agent" not in selected_agents:
            selected_agents.append(
                "itinerary_agent"
            )

        constraints = data.get(
            "trip_constraints",
            {}
        )

        if not isinstance(
            constraints,
            dict
        ):
            constraints = {}

        clean_constraints = (
            _empty_constraints()
        )

        for key in clean_constraints:

            if key in constraints:

                value = constraints[key]

                if key == "special_preferences":

                    if isinstance(
                        value,
                        list
                    ):
                        clean_constraints[key] = value

                else:

                    clean_constraints[key] = str(
                        value or ""
                    )

        reasoning = str(
            data.get(
                "reasoning",
                ""
            )
        )

    except Exception as exc:

        print(
            "SUPERVISOR ERROR:",
            type(exc).__name__,
            exc,
            flush=True,
        )

        # Safe fallback.
        selected_agents = [
            "flight_agent",
            "hotel_agent",
            "weather_agent",
            "budget_agent",
            "itinerary_agent",
        ]

        clean_constraints = (
            _empty_constraints()
        )

        reasoning = (
            "Supervisor fallback selected "
            "all travel specialists."
        )

    return {
        "selected_agents": selected_agents,
        "trip_constraints": clean_constraints,
        "supervisor_reasoning": reasoning,
        "messages": [
            AIMessage(
                content=(
                    "Travel specialists selected."
                )
            )
        ],
        "llm_calls": (
            state.get("llm_calls", 0) + 1
        ),
    }





# =========================================================
# FLIGHT AGENT
# =========================================================

FLIGHT_AGENT_PROMPT = """
You are a travel flight planning specialist.

User request:
{query}

Trip constraints:
{constraints}

Aviation information:
{aviation_data}

IMPORTANT:

The aviation data may contain an API restriction
or may only provide general airport/airline
information.

NEVER invent:

- flight numbers
- exact departure times
- exact arrival times
- exact ticket prices
- booking confirmation
- live availability

If live flight information is unavailable,
clearly state:

"Live flight details are currently unavailable."

Then provide useful general guidance using
only the information available.

Return concise travel guidance containing:

1. Departure airport
2. Arrival airport
3. Airlines, only if supported by the data
4. Typical flight duration, only if supported
5. Estimated airfare range, only if clearly marked estimate
6. Booking advice
"""


def _aviation_data_is_unavailable(
    data
) -> bool:

    text = str(data).lower()

    unavailable_markers = [
        "function_access_restricted",
        "api_error",
        "subscription plan",
        "not support this api function",
        '"ok": false',
        "'ok': false",
    ]

    return any(
        marker in text
        for marker in unavailable_markers
    )


def flight_agent(
    state: TravelState,
):

    print(
        "\nINSIDE FLIGHT AGENT\n",
        flush=True
    )

    query = state["user_query"]

    constraints = state.get(
        "trip_constraints",
        {}
    )

    try:

        airports = asyncio.run(
            aviation_mcp_call(
                "list_airports"
            )
        )

        airlines = asyncio.run(
            aviation_mcp_call(
                "list_airlines"
            )
        )

        print(
            "\nAIRPORTS:",
            airports,
            flush=True
        )

        print(
            "\nAIRLINES:",
            airlines,
            flush=True
        )

        if (
            _aviation_data_is_unavailable(
                airports
            )
            or _aviation_data_is_unavailable(
                airlines
            )
        ):

            flight_data = (
                "Live flight details are currently unavailable "
                "because the connected aviation data source "
                "does not provide the required live API functions "
                "under the current plan.\n\n"
                "Use a flight booking platform to verify "
                "current schedules, flight numbers, availability, "
                "and prices before booking."
            )

        else:

            prompt = FLIGHT_AGENT_PROMPT.format(
                query=query,
                constraints=constraints,
                aviation_data=(
                    f"AIRPORT DATA:\n"
                    f"{str(airports)[:4000]}\n\n"
                    f"AIRLINE DATA:\n"
                    f"{str(airlines)[:4000]}"
                ),
            )

            response = llm.invoke(
                [
                    SystemMessage(
                        content=(
                            "You are an expert travel "
                            "flight planner. "
                            "Never fabricate live flight data."
                        )
                    ),
                    HumanMessage(
                        content=prompt
                    ),
                ]
            )

            flight_data = str(
                response.content
            )

    except Exception as exc:

        print(
            "FLIGHT AGENT MCP ERROR:",
            type(exc).__name__,
            exc,
            flush=True,
        )

        flight_data = (
            "Live flight details are currently unavailable.\n\n"
            "Please verify current flight schedules, "
            "flight numbers, availability, and prices "
            "before booking."
        )

    return {
        "flight_results": flight_data,
        "messages": [
            AIMessage(
                content=(
                    "Flight recommendations generated."
                )
            )
        ],
        "llm_calls": (
            state.get("llm_calls", 0) + 1
        ),
    }


# =========================================================
# HOTEL SEARCH CLEANING
# =========================================================

HOTEL_CLEANER_PROMPT = """
You are a hotel recommendation specialist.

The text below comes from web search results.

Your job is to extract useful hotel information
and REMOVE webpage junk.

REMOVE things such as:

- Check-in
- Check-out
- Search buttons
- Calendar dates
- October 2026
- November 2026
- guest selectors
- room selectors
- navigation menus
- cookie notices
- generic booking UI
- unrelated webpage text

DO NOT invent:

- hotel prices
- ratings
- room availability
- booking confirmation
- exact facilities unless supported
- exact distance unless supported

Only use information present in the search results.

If price is not clearly present, say:
"Price not provided in search results."

Return a clean Markdown list.

For each useful hotel, use:

### Hotel Name
- Location: ...
- Price: ... or "Price not provided in search results."
- Rating: ... if available
- Highlights: ...
- Source: ...

Keep only the 5 most relevant hotels.

SEARCH RESULTS:
{results}
"""


def _clean_hotel_results_with_llm(
    raw_results: str,
) -> str:

    if not raw_results:

        return (
            "No relevant hotel search results were found."
        )

    try:

        prompt = HOTEL_CLEANER_PROMPT.format(
            results=raw_results[:12000]
        )

        response = llm.invoke(
            [
                SystemMessage(
                    content=(
                        "You clean hotel search results. "
                        "Never fabricate hotel information."
                    )
                ),
                HumanMessage(
                    content=prompt
                ),
            ]
        )

        cleaned = str(
            response.content
        ).strip()

        if not cleaned:

            return (
                "No useful hotel information "
                "was extracted from the search results."
            )

        return cleaned

    except Exception as exc:

        print(
            "HOTEL CLEANING ERROR:",
            type(exc).__name__,
            exc,
            flush=True,
        )

        return (
            "Hotel search completed, but the "
            "results could not be cleanly summarized. "
            "Please verify hotel details before booking."
        )


# =========================================================
# HOTEL AGENT
# =========================================================

def hotel_agent(
    state: TravelState,
):

    constraints = state.get(
        "trip_constraints",
        {}
    )

    destination = constraints.get(
        "destination",
        ""
    )

    duration = constraints.get(
        "duration",
        ""
    )

    budget = constraints.get(
        "budget",
        ""
    )

    travel_style = constraints.get(
        "travel_style",
        ""
    )

    if destination:

        query_parts = [
            f"best hotels and resorts in {destination}",
            "hotel accommodation recommendations",
            "best areas to stay",
            "hotel prices and reviews",
        ]

        if duration:

            query_parts.append(
                f"for a {duration} trip"
            )

        if budget:

            query_parts.append(
                f"budget {budget}"
            )

        if travel_style:

            query_parts.append(
                f"{travel_style} travel"
            )

        query = " ".join(
            query_parts
        )

    else:

        query = (
            "best hotels and resorts "
            "accommodation recommendations "
            f"for {state['user_query']}"
        )

    print(
        "\nHOTEL SEARCH QUERY:",
        query,
        flush=True
    )

    try:

        raw_hotel_results = asyncio.run(
            tavily_mcp_search(query)
        )

        print(
            "\nRAW HOTEL SEARCH COMPLETED",
            flush=True
        )

        hotel_results = (
            _clean_hotel_results_with_llm(
                str(raw_hotel_results)
            )
        )

    except Exception as exc:

        print(
            "HOTEL AGENT MCP ERROR:",
            type(exc).__name__,
            exc,
            flush=True,
        )

        hotel_results = (
            "Live hotel search is temporarily unavailable.\n\n"
            "Please verify current accommodation "
            "availability and prices before booking."
        )

    return {
        "hotel_results": str(
            hotel_results
        ),
        "messages": [
            AIMessage(
                content=(
                    "Hotel recommendations generated."
                )
            )
        ],
        "llm_calls": (
            state.get("llm_calls", 0) + 1
        ),
    }


# =========================================================
# WEATHER AGENT
# =========================================================

def weather_agent(
    state: TravelState,
):

    constraints = state.get(
        "trip_constraints",
        {}
    )

    city = constraints.get(
        "destination",
        ""
    )

    if not city:

        try:

            city = extract_destination(
                state["user_query"]
            )

        except Exception:

            city = ""

    if not city:

        return {
            "weather_results": (
                "Weather information could not be "
                "determined because the destination "
                "was not specified."
            ),
            "messages": [
                AIMessage(
                    content=(
                        "Weather information "
                        "could not be determined."
                    )
                )
            ],
        }

    try:

        weather_data = asyncio.run(
            weather_mcp_search(city)
        )

        forecast_data = asyncio.run(
            forecast_mcp_search(city)
        )

        weather_results = f"""
### Current Weather

{weather_data}

### Forecast

{forecast_data}
"""

    except Exception as exc:

        print(
            "WEATHER AGENT MCP ERROR:",
            type(exc).__name__,
            exc,
            flush=True,
        )

        weather_results = (
            f"Live weather information for {city} "
            "is temporarily unavailable.\n\n"
            "Use general seasonal guidance only and "
            "verify the weather forecast before departure."
        )

    return {
        "weather_results": weather_results,
        "messages": [
            AIMessage(
                content=(
                    "Weather information generated."
                )
            )
        ],
    }


# =========================================================
# BUDGET AGENT
# =========================================================

BUDGET_PROMPT = """
You are a travel budget planning specialist.

USER REQUEST:
{query}

TRIP CONSTRAINTS:
{constraints}

AVAILABLE FLIGHT INFORMATION:
{flight_results}

AVAILABLE HOTEL INFORMATION:
{hotel_results}

Create a realistic budget estimate.

IMPORTANT:

1. If the user gave a total budget, respect it.
2. Never silently increase the user's budget.
3. If the budget appears unrealistic, clearly explain why.
4. Do not invent exact live prices.
5. Use ranges for estimated costs.
6. Clearly label estimates.
7. Do not treat hotel search recommendations as confirmed prices.
8. Do not invent flight prices when live flight data is unavailable.

Return concise Markdown.

Include:

- Flights
- Hotels
- Food
- Local transport
- Activities
- Miscellaneous
- Estimated total
- Budget feasibility
"""


def budget_agent(
    state: TravelState,
):

    try:

        prompt = BUDGET_PROMPT.format(
            query=state["user_query"],
            constraints=state.get(
                "trip_constraints",
                {}
            ),
            flight_results=state.get(
                "flight_results",
                ""
            ),
            hotel_results=state.get(
                "hotel_results",
                ""
            ),
        )

        response = llm.invoke(
            [
                SystemMessage(
                    content=(
                        "You are a careful travel "
                        "budget planner. "
                        "Never fabricate live prices."
                    )
                ),
                HumanMessage(
                    content=prompt
                ),
            ]
        )

        budget_results = str(
            response.content
        )

    except Exception as exc:

        print(
            "BUDGET AGENT ERROR:",
            type(exc).__name__,
            exc,
            flush=True,
        )

        budget_results = (
            "A detailed budget estimate could not "
            "be generated. Use current flight, hotel, "
            "food, transport, and activity prices "
            "to verify the total before booking."
        )

    return {
        "budget_results": budget_results,
        "messages": [
            AIMessage(
                content=(
                    "Budget estimate generated."
                )
            )
        ],
        "llm_calls": (
            state.get("llm_calls", 0) + 1
        ),
    }


# =========================================================
# ITINERARY AGENT
# =========================================================

def itinerary_agent(
    state: TravelState,
):

    prompt = f"""
You are the final travel itinerary planner
for Rahi-Go.

IMPORTANT RULES:

1. Use the user's ORIGINAL REQUEST as the PRIMARY source.
2. Respect the user's destination, origin, duration,
   travelers, budget, and preferences.
3. NEVER invent exact flight numbers.
4. NEVER invent exact flight timings.
5. NEVER invent booking confirmations.
6. NEVER invent live hotel availability.
7. NEVER invent hotel prices.
8. Never invent exact travel dates.
9. If the user did not provide travel dates,
   write:
   "Dates not specified"
10. Do NOT use old dates such as 2024.
11. Do NOT silently increase the user's budget.
12. If the requested budget is unrealistic,
   explain the constraint honestly.
13. Search results are recommendations,
   not confirmed bookings.
14. Clearly distinguish:
   - Search-based information
   - Estimated information
   - General recommendations
15. If live flight data is unavailable,
   write:
   "Live flight details are currently unavailable."
16. If live weather data is unavailable,
   clearly say so.
17. Hotel prices may ONLY be mentioned if they
   actually appear in the hotel search information.
18. Keep the itinerary practical and concise.

USER REQUEST:
{state["user_query"]}

TRIP CONSTRAINTS:
{state.get("trip_constraints", {})}

FLIGHT AGENT RESULTS:
{state.get("flight_results", "")}

HOTEL AGENT RESULTS:
{state.get("hotel_results", "")}

WEATHER AGENT RESULTS:
{state.get("weather_results", "")}

BUDGET AGENT RESULTS:
{state.get("budget_results", "")}

Create a DRAFT travel itinerary for human review.

Use exactly this structure:

# [Duration] [Destination] Trip

## Trip Summary

- Destination
- Origin
- Travelers
- Duration
- Budget
- Dates

## 1. Flights

Give useful flight guidance.

If live flight information is unavailable,
say so clearly.

Never create fake flight numbers,
times, or exact prices.

## 2. Hotels

Recommend hotels based on the search results.

Do not invent prices.

If a price is unavailable, simply say:
"Price not provided in search results."

## 3. Daily Itinerary

Create a practical day-by-day itinerary.

Do not invent dates.

Use:
Day 1
Day 2
Day 3
etc.

## 4. Weather

Use the weather information provided.

Clearly identify whether the information
is live or general.

## 5. Budget

Use the user's requested budget.

Break costs into:

- Flights
- Hotels
- Food
- Local transport
- Activities
- Miscellaneous

Clearly label estimates.

## 6. Important Notes

Mention what the traveler must verify
before booking.

End with:

"Draft itinerary prepared for human review."
"""

    try:

        response = llm.invoke(
            [
                SystemMessage(
                    content=(
                        "You are a careful travel planner. "
                        "Never fabricate travel data. "
                        "Use only the information provided."
                    )
                ),
                HumanMessage(
                    content=prompt
                ),
            ]
        )

        itinerary = str(
            response.content
        )

    except Exception as exc:

        print(
            "ITINERARY AGENT ERROR:",
            type(exc).__name__,
            exc,
            flush=True,
        )

        itinerary = (
            "Unable to generate the itinerary "
            "at this time. Please try again."
        )

    approval_request = (
        "Please review the generated draft itinerary. "
        "Approve it to create the final polished plan, "
        "or provide feedback for revision."
    )

    return {
        "itinerary": itinerary,
        "approval_request": approval_request,
        "messages": [
            AIMessage(
                content=(
                    "Draft itinerary created "
                    "for human review."
                )
            )
        ],
        "llm_calls": (
            state.get("llm_calls", 0) + 1
        ),
    }


# =========================================================
# HUMAN APPROVAL
# =========================================================

def human_approval_agent(
    state: TravelState,
):

    review = interrupt(
        {
            "question": (
                "Do you approve this itinerary?"
            ),

            "draft_itinerary": state.get(
                "itinerary",
                ""
            ),

            "approval_request": state.get(
                "approval_request",
                ""
            ),

            "selected_agents": state.get(
                "selected_agents",
                []
            ),

            "supervisor_reasoning": state.get(
                "supervisor_reasoning",
                ""
            ),

            "expected_response": {
                "approved": True,
                "feedback": (
                    "Optional revision feedback"
                ),
            },
        }
    )

    if not isinstance(
        review,
        dict
    ):
        review = {}

    approved = bool(
        review.get(
            "approved",
            False
        )
    )

    human_feedback = str(
        review.get(
            "feedback",
            ""
        )
    ).strip()

    return {
        "approved": approved,
        "human_feedback": human_feedback,
        "messages": [
            AIMessage(
                content=(
                    "Human approval step completed."
                )
            )
        ],
    }


# =========================================================
# FINAL AGENT
# =========================================================

FINAL_AGENT_PROMPT = """
You are the final response agent for Rahi-Go.

Original user request:
{query}

Draft itinerary:
{itinerary}

Human approval:
{approved}

Human feedback:
{feedback}

Create the final polished travel response.

Rules:

1. If approved is true:
   - present the itinerary clearly
   - keep important verification notes
   - do not introduce fabricated data

2. If approved is false and feedback exists:
   - explain that the draft was not approved
   - incorporate the feedback into a revised response
   - do not fabricate missing travel data

3. Never invent:
   - flight numbers
   - exact flight schedules
   - hotel availability
   - booking confirmations
   - exact prices not present in the supplied information

4. Keep the response practical and easy to read.
"""


def final_agent(
    state: TravelState,
):

    approved = bool(
        state.get(
            "approved",
            False
        )
    )

    feedback = state.get(
        "human_feedback",
        ""
    )

    itinerary = state.get(
        "itinerary",
        ""
    )

    # -----------------------------------------------------
    # If user rejected the draft and gave feedback,
    # generate a revised plan.
    # -----------------------------------------------------

    if (
        not approved
        and feedback
    ):

        try:

            prompt = FINAL_AGENT_PROMPT.format(
                query=state["user_query"],
                itinerary=itinerary,
                approved=approved,
                feedback=feedback,
            )

            response = llm.invoke(
                [
                    SystemMessage(
                        content=(
                            "You are a careful final "
                            "travel response planner."
                        )
                    ),
                    HumanMessage(
                        content=prompt
                    ),
                ]
            )

            final_response = str(
                response.content
            )

        except Exception as exc:

            print(
                "FINAL AGENT ERROR:",
                type(exc).__name__,
                exc,
                flush=True,
            )

            final_response = itinerary

    else:

        final_response = itinerary

    return {
        "final_response": final_response,
        "messages": [
            AIMessage(
                content=(
                    "Final travel plan prepared."
                )
            )
        ],
        "llm_calls": (
            state.get("llm_calls", 0) + 1
        ),
    }


# =========================================================
# ROUTING
# =========================================================

ROUTE_MAP = {

    "guardrail_blocked":
        "guardrail_blocked",

    "flight_agent":
        "flight_agent",

    "hotel_agent":
        "hotel_agent",

    "weather_agent":
        "weather_agent",

    "budget_agent":
        "budget_agent",

    "itinerary_agent":
        "itinerary_agent",
}


def _selected_agents(
    state: TravelState,
) -> list[str]:

    selected = state.get(
        "selected_agents",
        []
    )

    return [
        agent
        for agent in AGENT_ORDER
        if agent in selected
    ]


def route_from_supervisor(
    state: TravelState,
) -> str:

    if not state.get(
        "guardrail_allowed",
        True
    ):

        return "guardrail_blocked"

    selected = _selected_agents(
        state
    )

    if selected:

        return selected[0]

    return "itinerary_agent"


def route_after_agent(
    current_agent: str,
):

    def route(
        state: TravelState,
    ) -> str:

        selected = _selected_agents(
            state
        )

        try:

            current_index = (
                AGENT_ORDER.index(
                    current_agent
                )
            )

        except ValueError:

            return "itinerary_agent"

        for next_agent in AGENT_ORDER[
            current_index + 1:
        ]:

            if next_agent in selected:

                return next_agent

        return "itinerary_agent"

    return route


# =========================================================
# GRAPH
# =========================================================

graph = StateGraph(
    TravelState
)


graph.add_node(
    "supervisor",
    supervisor_agent
)

graph.add_node(
    "guardrail_blocked",
    guardrail_blocked_agent
)

graph.add_node(
    "flight_agent",
    flight_agent
)

graph.add_node(
    "hotel_agent",
    hotel_agent
)

graph.add_node(
    "weather_agent",
    weather_agent
)

graph.add_node(
    "budget_agent",
    budget_agent
)

graph.add_node(
    "itinerary_agent",
    itinerary_agent
)

graph.add_node(
    "human_approval",
    human_approval_agent
)

graph.add_node(
    "final_agent",
    final_agent
)


# ---------------------------------------------------------
# Main flow
# ---------------------------------------------------------

graph.add_edge(
    START,
    "supervisor"
)


graph.add_conditional_edges(
    "supervisor",
    route_from_supervisor,
    ROUTE_MAP
)


# ---------------------------------------------------------
# Dynamic specialist routing
# ---------------------------------------------------------

graph.add_conditional_edges(
    "flight_agent",
    route_after_agent(
        "flight_agent"
    ),
    ROUTE_MAP
)


graph.add_conditional_edges(
    "hotel_agent",
    route_after_agent(
        "hotel_agent"
    ),
    ROUTE_MAP
)


graph.add_conditional_edges(
    "weather_agent",
    route_after_agent(
        "weather_agent"
    ),
    ROUTE_MAP
)


graph.add_conditional_edges(
    "budget_agent",
    route_after_agent(
        "budget_agent"
    ),
    ROUTE_MAP
)


# ---------------------------------------------------------
# Itinerary → HITL → Final
# ---------------------------------------------------------

graph.add_edge(
    "itinerary_agent",
    "human_approval"
)


graph.add_edge(
    "human_approval",
    "final_agent"
)


graph.add_edge(
    "final_agent",
    END
)


graph.add_edge(
    "guardrail_blocked",
    END
)


# =========================================================
# POSTGRES CHECKPOINTING
# =========================================================

DATABASE_URL = get_database_url()


_conn = psycopg.connect(
    DATABASE_URL,
    autocommit=True,
    row_factory=dict_row,
    connect_timeout=10,
    keepalives=1,
    keepalives_idle=30,
    keepalives_interval=10,
    keepalives_count=5,
)


checkpointer = PostgresSaver(
    _conn
)


checkpointer.setup()


travel_graph = graph.compile(
    checkpointer=checkpointer
)


# =========================================================
# RESULT SERIALIZATION
# =========================================================

def _interrupt_payload(
    result: dict[str, Any],
):

    interrupts = result.get(
        "__interrupt__",
        []
    )

    if not interrupts:

        return None

    first_interrupt = interrupts[0]

    payload = getattr(
        first_interrupt,
        "value",
        first_interrupt
    )

    if isinstance(
        payload,
        dict
    ):

        return payload

    return {
        "value": payload
    }


def _serialize_result(
    result: dict[str, Any],
    thread_id: str,
):

    messages = result.get(
        "messages",
        []
    )

    last_message = ""

    if messages:

        last_message = str(
            messages[-1].content
        )

    answer = (
        result.get(
            "final_response"
        )
        or last_message
    )

    interrupt_payload = (
        _interrupt_payload(
            result
        )
    )

    if interrupt_payload:

        answer = (
            interrupt_payload.get(
                "draft_itinerary"
            )
            or result.get(
                "itinerary",
                ""
            )
        )

    return {

        "thread_id":
            thread_id,

        "answer":
            answer,

        "requires_approval":
            interrupt_payload is not None,

        "approval_request":
            (
                interrupt_payload.get(
                    "approval_request",
                    ""
                )
                if interrupt_payload
                else result.get(
                    "approval_request",
                    ""
                )
            ),

        "flight_results":
            result.get(
                "flight_results",
                ""
            ),

        "hotel_results":
            result.get(
                "hotel_results",
                ""
            ),

        "weather_results":
            result.get(
                "weather_results",
                ""
            ),

        "budget_results":
            result.get(
                "budget_results",
                ""
            ),

        "itinerary":
            (
                interrupt_payload.get(
                    "draft_itinerary",
                    ""
                )
                if interrupt_payload
                else result.get(
                    "itinerary",
                    ""
                )
            ),

        "selected_agents":
            result.get(
                "selected_agents",
                []
            ),

        "trip_constraints":
            result.get(
                "trip_constraints",
                {}
            ),

        "supervisor_reasoning":
            result.get(
                "supervisor_reasoning",
                ""
            ),

        "guardrail_allowed":
            result.get(
                "guardrail_allowed",
                True
            ),

        "guardrail_reason":
            result.get(
                "guardrail_reason",
                ""
            ),

        "approved":
            result.get(
                "approved"
            ),

        "human_feedback":
            result.get(
                "human_feedback",
                ""
            ),

        "llm_calls":
            result.get(
                "llm_calls",
                0
            ),
    }


# =========================================================
# RUN TRAVEL AGENT
# =========================================================

def run_travel_agent(
    user_input: str,
    thread_id: str | None = None,
):

    if not thread_id:

        thread_id = (
            f"user_{uuid.uuid4().hex}"
        )

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    initial_state = {

        "messages": [
            HumanMessage(
                content=user_input
            )
        ],

        "user_query":
            user_input,

        "guardrail_allowed":
            True,

        "guardrail_reason":
            "",

        "selected_agents":
            [],

        "trip_constraints":
            _empty_constraints(),

        "supervisor_reasoning":
            "",

        "flight_results":
            "",

        "hotel_results":
            "",

        "weather_results":
            "",

        "budget_results":
            "",

        "itinerary":
            "",

        "approval_request":
            "",

        "approved":
            False,

        "human_feedback":
            "",

        "final_response":
            "",

        "llm_calls":
            0,
    }

    result = travel_graph.invoke(
        initial_state,
        config=config,
    )

    return _serialize_result(
        result,
        thread_id,
    )


# =========================================================
# RESUME AFTER HUMAN APPROVAL
# =========================================================

def resume_travel_agent(
    thread_id: str,
    approved: bool,
    feedback: str = "",
):

    if not thread_id:

        raise ValueError(
            "thread_id is required "
            "to resume a travel plan."
        )

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    result = travel_graph.invoke(
        Command(
            resume={
                "approved": approved,
                "feedback": feedback.strip(),
            }
        ),
        config=config,
    )

    return _serialize_result(
        result,
        thread_id,
    )

