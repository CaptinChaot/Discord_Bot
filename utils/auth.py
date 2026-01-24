from fastapi import Request, HTTPException

def require_auth(request: Request):
    """
    Prüft, ob eine gültige Admin-Session existiert.
    """
    if not request.session.get("auth"):
        raise HTTPException(status_code=401, detail="Not authenticated")
