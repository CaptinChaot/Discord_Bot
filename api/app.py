import os
from fastapi import FastAPI, Request, Depends, HTTPException
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

from utils.auth import require_auth

load_dotenv()

def create_api(bot):
    app = FastAPI(title="ChaosBot API")

    # ---------------------------
    # Session Middleware
    # ---------------------------
    app.add_middleware(
        SessionMiddleware,
        secret_key=os.getenv("CHAOSBOT_SESSION_SECRET"),
        https_only=False  # später True mit HTTPS
    )

    # ---------------------------
    # LOGIN
    # ---------------------------
    @app.post("/login")
    async def login(data: dict, request: Request):
        if data.get("passphrase") != os.getenv("BOT_ADMIN_PASSPHRASE"):
            raise HTTPException(status_code=403, detail="Invalid credentials")

        request.session["auth"] = True
        return {"ok": True}

    # ---------------------------
    # LOGOUT (optional, aber gut)
    # ---------------------------
    @app.post("/logout")
    async def logout(request: Request):
        request.session.clear()
        return {"ok": True}

    # ---------------------------
    # API ENDPOINTS (GESCHÜTZT)
    # ---------------------------
    @app.get("/api/dashboard", dependencies=[Depends(require_auth)])
    async def dashboard():
        return {
            "server": {
                "name": bot.guilds[0].name if bot.guilds else "—",
                "users": bot.guilds[0].member_count if bot.guilds else 0
            },
            "stats": {
                "warns": 0,
                "activeUsers": 0,
                "bot": {
                    "status": "ONLINE" if bot.is_ready() else "OFFLINE",
                    "latency": round(bot.latency * 1000)
                }
            }
        }

    @app.get("/api/users", dependencies=[Depends(require_auth)])
    async def users():
        return {"users": []}

    @app.post("/api/mod/action", dependencies=[Depends(require_auth)])
    async def mod_action(data: dict):
        # hier später handle_mod_action()
        return {"ok": True, "message": "action received"}

    return app
