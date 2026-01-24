from fastapi import Header, HTTPException

API_TOKEN = "CHANGE_ME_LONG_RANDOM"

def verify_token(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing token")

    token = authorization.split(" ", 1)[1]
    if token != API_TOKEN:
        raise HTTPException(403, "Invalid token")
