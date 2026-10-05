from pathlib import Path
import traceback
import uvicorn

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from backend import run_travel_agent, resume_travel_agent

import nest_asyncio
nest_asyncio.apply()


BASE_DIR = Path(__file__).resolve().parent


app = FastAPI(
    title="Rahi-Go",
    description="LangGraph Multi-Agent Travel Planner with FastAPI Frontend",
    version="1.0.0"
)


# =========================================================
# STATIC FILES
# =========================================================

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static"
)


# =========================================================
# TEMPLATES
# =========================================================

Frontend = Jinja2Templates(
    directory=str(BASE_DIR / "Frontend")
)


# =========================================================
# REQUEST MODELS
# =========================================================

class TravelRequest(BaseModel):
    message: str
    thread_id: str | None = None


class ApprovalRequest(BaseModel):
    thread_id: str
    approved: bool
    feedback: str = ""


# =========================================================
# HOME
# =========================================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return Frontend.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )


# =========================================================
# START TRAVEL PLAN
# =========================================================

@app.post("/api/travel")
async def travel_planner(request_data: TravelRequest):

    try:

        user_message = request_data.message.strip()

        if not user_message:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Message cannot be empty."
                }
            )


        result = run_travel_agent(
            user_input=user_message,
            thread_id=request_data.thread_id
        )


        return JSONResponse(
            content={
                "success": True,

                "thread_id": result["thread_id"],

                "answer": result["answer"],

                "requires_approval": result.get(
                    "requires_approval",
                    False
                ),

                "approval_request": result.get(
                    "approval_request",
                    ""
                ),

                "flight_results": result.get(
                    "flight_results",
                    ""
                ),

                "hotel_results": result.get(
                    "hotel_results",
                    ""
                ),

                "weather_results": result.get(
                    "weather_results",
                    ""
                ),

                "budget_results": result.get(
                    "budget_results",
                    ""
                ),

                "itinerary": result.get(
                    "itinerary",
                    ""
                ),

                "selected_agents": result.get(
                    "selected_agents",
                    []
                ),

                "trip_constraints": result.get(
                    "trip_constraints",
                    {}
                ),

                "supervisor_reasoning": result.get(
                    "supervisor_reasoning",
                    ""
                ),

                "approved": result.get(
                    "approved",
                    False
                ),

                "human_feedback": result.get(
                    "human_feedback",
                    ""
                ),

                "llm_calls": result.get(
                    "llm_calls",
                    0
                )
            }
        )


    except Exception as e:

        print("ERROR:", e)
        traceback.print_exc()

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e)
            }
        )


# =========================================================
# APPROVE / REVISE TRAVEL PLAN
# =========================================================

@app.post("/api/travel/approval")
async def travel_approval(
    request_data: ApprovalRequest
):

    try:

        result = resume_travel_agent(
            thread_id=request_data.thread_id,
            approved=request_data.approved,
            feedback=request_data.feedback
        )


        return JSONResponse(
            content={
                "success": True,

                "thread_id": result["thread_id"],

                "answer": result["answer"],

                "requires_approval": result.get(
                    "requires_approval",
                    False
                ),

                "approval_request": result.get(
                    "approval_request",
                    ""
                ),

                "flight_results": result.get(
                    "flight_results",
                    ""
                ),

                "hotel_results": result.get(
                    "hotel_results",
                    ""
                ),

                "weather_results": result.get(
                    "weather_results",
                    ""
                ),

                "budget_results": result.get(
                    "budget_results",
                    ""
                ),

                "itinerary": result.get(
                    "itinerary",
                    ""
                ),

                "approved": result.get(
                    "approved",
                    False
                ),

                "human_feedback": result.get(
                    "human_feedback",
                    ""
                ),

                "llm_calls": result.get(
                    "llm_calls",
                    0
                )
            }
        )


    except Exception as e:

        print("APPROVAL ERROR:", e)
        traceback.print_exc()

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e)
            }
        )


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
async def health_check():

    return {
        "status": "ok",
        "message": "AI Travel Planner API is running"
    }


# =========================================================
# FAVICON
# =========================================================

@app.get("/favicon.ico")
async def favicon():

    return JSONResponse(content={})


# =========================================================
# RUN SERVER
# =========================================================

if __name__ == "__main__":

    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=8000,
        reload=False
    )