from fastapi import APIRouter
from wrangler.schedule_logic import get_next_session, get_current_session
from wrangler.schedule_data import CONFERENCE_DATA

def build_schedule_router() -> APIRouter:
    router = APIRouter(prefix="/api/schedule", tags=["schedule"])

    @router.get("/next")
    def next_session():
        session, time_str = get_next_session()
        return {
            "session": session,
            "next_time": time_str
        }

    @router.get("/current")
    def current_session():
        session_info = get_current_session()
        if session_info:
            session, time_str = session_info
            return {
                "session": session,
                "time": time_str
            }
        return {"session": None}

    @router.get("/all")
    def all_sessions():
        return CONFERENCE_DATA

    return router
