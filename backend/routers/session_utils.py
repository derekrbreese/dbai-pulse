"""
Helpers for session-backed user identity in API routers.
"""

from fastapi import HTTPException, Request


def get_authenticated_user_id(request: Request) -> str:
    """Return authenticated user id from session or raise 401."""
    user_id = request.session.get("auth_user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Login required.")
    return str(user_id)
