# ✈️ Rahi-Go — AI-Powered Multi-Agent Travel Planner

Rahi-Go is an **AI-powered multi-agent travel planning system** built with **LangGraph, LangChain, MCP, Groq, Tavily, PostgreSQL, FastAPI, and Human-in-the-Loop (HITL)**.

It takes a user's natural-language travel request and dynamically coordinates specialized AI agents for **flights, hotels, weather, budget planning, and itinerary generation**.

The system also includes **guardrails, persistent conversation state, dynamic agent routing, and human approval** before finalizing the travel plan.

---

## 🚀 Key Features

* 🤖 **Multi-Agent Architecture**

  * Supervisor agent dynamically decides which specialist agents are required.
  * Flight, hotel, weather, budget, and itinerary agents work as specialized components.

* 🧠 **LangGraph Workflow**

  * State-based agent orchestration.
  * Dynamic routing between agents.
  * Persistent execution state.

* 🔌 **Model Context Protocol (MCP)**

  * Integrates external tools through MCP.
  * AviationStack MCP for flight-data integration.
  * Tavily MCP for web search.
  * Weather MCP for weather information.

* 🛡️ **AI Guardrails**

  * Filters requests before specialist agents are executed.
  * Prevents irrelevant or unsafe travel-related requests from entering the workflow.

* 👤 **Human-in-the-Loop (HITL)**

  * The generated itinerary is presented for human approval.
  * Users can approve or reject the itinerary.
  * Feedback can be provided for itinerary revision.

* 💾 **PostgreSQL Persistence**

  * LangGraph checkpoints are stored using PostgreSQL.
  * Conversation/workflow state can persist across requests.

* 🏨 **Hotel Search**

  * Uses Tavily web search.
  * Search results are cleaned before being presented to the user.

* ✈️ **Flight Data**

  * AviationStack integration through MCP.
  * Provides available flight/status information when supported by the API plan.

* 💰 **Budget Planning**

  * Generates an estimated travel budget based on user requirements.
  * Respects the user's specified budget instead of silently increasing it.

* 🗓️ **Itinerary Generation**

  * Creates a structured day-by-day itinerary.
  * Avoids inventing dates, flight numbers, booking confirmations, or unavailable prices.

---

## 🏗️ Architecture

```text
                         ┌──────────────────┐
                         │      User        │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │    FastAPI       │
                         │     Backend      │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │   Supervisor     │
                         │      Agent       │
                         └────────┬─────────┘
                                  │
                         Dynamic Routing
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
          ▼                       ▼                       ▼
   ┌─────────────┐        ┌─────────────┐        ┌─────────────┐
   │   Flight    │        │    Hotel    │        │   Weather   │
   │    Agent    │        │    Agent    │        │    Agent    │
   └──────┬──────┘        └──────┬──────┘        └──────┬──────┘
          │                      │                      │
          ▼                      ▼                      ▼
   AviationStack              Tavily               Weather MCP


          ┌───────────────────────┴───────────────────────┐
                                  │
                                  ▼
                         ┌──────────────────┐
                         │  Budget Agent    │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │ Itinerary Agent  │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │ Human Approval   │
                         │      HITL        │
                         └────────┬─────────┘
                                  │
                         Approve / Feedback
                                  │
                                  ▼
                         ┌──────────────────┐
                         │   Final Agent    │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │  Final Response  │
                         └──────────────────┘

                    PostgreSQL
                       ▲
                       │
               LangGraph Checkpoint
```

---

## 🔄 Workflow

### 1. User Request

The user provides a natural-language travel request such as:

```text
Plan a 4-day trip to Jaipur from Delhi with a budget of ₹30,000.
```

### 2. Supervisor Agent

The supervisor analyzes the request and determines which specialist agents are required.

For example:

```text
Flight Agent
Hotel Agent
Weather Agent
Budget Agent
Itinerary Agent
```

### 3. Guardrail

The request passes through a guardrail layer that checks whether the request is relevant and appropriate for the travel-planning system.

### 4. Specialist Agents

The selected agents independently perform their responsibilities.

**Flight Agent**

* Retrieves available flight/status information through AviationStack MCP.
* Does not fabricate unavailable flight details.

**Hotel Agent**

* Searches the web through Tavily MCP.
* Extracts useful hotel information from search results.

**Weather Agent**

* Retrieves weather information for the destination.

**Budget Agent**

* Creates an estimated travel budget using the available information.

### 5. Itinerary Agent

The itinerary agent combines the collected information and generates a structured day-by-day travel plan.

### 6. Human Approval

Before the plan is finalized, the system pauses using LangGraph's interrupt mechanism.

The user can:

```text
Approve
```

or

```text
Reject + provide feedback
```

### 7. Final Agent

If approved, the itinerary is returned.

If rejected, the feedback is used to revise the itinerary.

---

## 🧰 Tech Stack

| Technology    | Purpose                            |
| ------------- | ---------------------------------- |
| Python        | Core programming language          |
| LangGraph     | Multi-agent workflow orchestration |
| LangChain     | LLM application framework          |
| Groq          | LLM inference                      |
| MCP           | External tool integration          |
| Tavily        | Web search                         |
| AviationStack | Flight-data integration            |
| PostgreSQL    | Persistent workflow state          |
| Psycopg       | PostgreSQL connection              |
| FastAPI       | Backend API                        |
| Jinja2        | Frontend templating                |
| JavaScript    | Frontend interaction               |
| LangSmith     | LLM tracing and debugging          |
| Render        | Deployment                         |

---

## 📁 Project Structure

```text
Rahi-Go/
│
├── app.py
├── backend.py
├── mcp_flight.py
├── weather_mcp.py
│
├── Frontend/
│   ├── templates/
│   ├── static/
│   └── ...
│
├── requirements.txt
├── .env
├── .gitignore
└── README.md
```

> `.env` should never be committed to GitHub.

---

## 🔐 Environment Variables

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key
TAVILY_API_KEY=your_tavily_api_key
AVIATIONSTACK_API_KEY=your_aviationstack_api_key
OPENWEATHER_API_KEY=your_openweather_api_key
DATABASE_URL=your_postgresql_database_url
```

The PostgreSQL connection is configured with SSL when required.

---

## ⚙️ Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/Mansi26-code1/Rahi-Go.git
cd Rahi-Go
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

### 3. Activate the environment

Windows CMD:

```cmd
venv\Scripts\activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure environment variables

Create `.env` and add the required API keys.

### 6. Run the application

```cmd
python app.py
```

The application runs locally at:

```text
http://127.0.0.1:8000
```

---

## 🧠 Example Queries

### Example 1

```text
Plan a 4-day trip to Jaipur from Delhi.
```

### Example 2

```text
Plan a 7-day Japan trip from Delhi with a budget of ₹1,00,000.
```

### Example 3

```text
Plan a Goa trip for 2 people with hotels, weather and budget.
```

The system extracts constraints such as:

```text
Destination
Origin
Duration
Budget
Travel style
Preferences
```

and uses them throughout the workflow.

---

## 👤 Human-in-the-Loop

Rahi-Go uses LangGraph's interrupt/resume mechanism for human approval.

The workflow can pause at:

```text
Itinerary Generated
        ↓
Human Review
        ↓
   ┌────┴────┐
   ↓         ↓
Approve    Reject
   ↓         ↓
 Final     Feedback
 Response    ↓
             ↓
       Revised Itinerary
```

This makes the system more suitable for workflows where an AI-generated result should not be finalized without human validation.

---

## 💾 Persistence

Rahi-Go uses **PostgreSQL with LangGraph's `PostgresSaver`** to persist graph state.

This allows the application to maintain workflow information such as:

* User query
* Selected agents
* Agent results
* Generated itinerary
* Human approval
* Human feedback
* Final response

Each travel workflow is associated with a unique `thread_id`.

---

## 🛡️ Reliability & Safety

The application is designed to avoid common LLM application problems:

### No fabricated flight details

If live flight data is unavailable, the application clearly reports the limitation instead of creating fake flight numbers or timings.

### No invented travel dates

If the user does not provide dates, the itinerary uses:

```text
Day 1
Day 2
Day 3
...
```

instead of assuming dates.

### Budget awareness

The budget agent uses the user's specified budget as a constraint.

### Search-result cleaning

Raw web search results may contain webpage navigation, booking controls, calendars, or unrelated text.

The hotel-search pipeline cleans these results before presenting them to the user.

---

## 📊 Observability

The project uses **LangSmith** for tracing and debugging LLM workflows.

This helps inspect:

* LLM calls
* Agent execution
* Prompts
* Outputs
* Workflow behavior
* Errors

---

## ⚠️ Current Limitations

* AviationStack availability depends on the API subscription plan.
* Flight-data integration is for flight/status information and does not provide guaranteed ticket booking or fare availability.
* Hotel information comes from web search results and should be verified before booking.
* Weather information depends on the configured weather service.
* Budget values are estimates and may change based on actual prices.
* Rahi-Go is a travel-planning assistant, not a booking platform.

---

## 🚀 Future Improvements

Potential future improvements include:

* 🔎 Hybrid hotel/flight search
* 💳 More accurate live fare APIs
* 🗺️ Interactive maps
* 📍 Location-aware recommendations
* 🧳 Personalized travel profiles
* 💬 Conversational trip modification
* 🧠 Better agent memory
* 📈 Cost and latency monitoring
* 🧪 Automated agent evaluation
* 🔐 Improved authentication and authorization
* 📱 Improved responsive UI
* ☁️ Production deployment and monitoring

---

## 🎯 Why Rahi-Go?

Traditional travel planners often use a fixed sequence of API calls.

Rahi-Go uses a **dynamic multi-agent architecture** where a supervisor determines which specialist capabilities are required for a particular request.

For example:

```text
Simple weather request
        ↓
Supervisor
        ↓
Weather Agent
```

while a complete trip request may become:

```text
Supervisor
   ↓
Flight Agent
   ↓
Hotel Agent
   ↓
Weather Agent
   ↓
Budget Agent
   ↓
Itinerary Agent
   ↓
Human Approval
   ↓
Final Agent
```

This demonstrates practical concepts in:

* Agentic AI
* Multi-agent orchestration
* LangGraph
* MCP
* Tool calling
* RAG/web search
* Human-in-the-loop systems
* State persistence
* LLM application safety
* API integration

---

## 👩‍💻 Author

**Mansi Pandey**

B.Tech Computer Science & Engineering

Interested in:

```text
AI Engineering
Generative AI
Agentic AI
Machine Learning
LLM Applications
```

GitHub: **Mansi26-code1**

---

## ⭐ Project Status

🚧 **Active Development**

Core multi-agent travel planning workflow is implemented with:

* LangGraph
* MCP
* Supervisor routing
* Specialized agents
* Guardrails
* Human-in-the-loop approval
* PostgreSQL persistence
* FastAPI backend
* Web-based frontend
* LangSmith tracing
