from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from utils.auth import verify_token

def create_api(bot):
    app = FastAPI(title="ChaosBot API")

    @app.get("/api/dashboard", dependencies=[Depends(verify_token)])
    async def dashboard():
        return {
            "server": {
                "name": bot.guilds[0].name if bot.guilds else "—",
                "users": bot.guilds[0].member_count if bot.guilds else 0,
            },
            "stats": {
                "warns": bot.warns_count(),   # deine Funktion
                "activeUsers": bot.active_users(),
                "bot": {
                    "status": "ONLINE" if bot.is_ready() else "OFFLINE",
                    "latency": round(bot.latency * 1000)
                }
            }
        }

    @app.get("/api/users", dependencies=[Depends(verify_token)])
    async def users():
        return {
            "users": bot.serialize_users()
        }

    class ModAction(BaseModel):
        action: str
        target_id: int
        reason: str
        timeout_minutes: int = 0
        source: str

    @app.post("/api/mod/action", dependencies=[Depends(verify_token)])
    async def mod_action(data: ModAction):
        ok, msg, log = await bot.handle_mod_action(data)
        if not ok:
            raise HTTPException(400, msg)
        return {"ok": True, "message": msg, "log": log}

    return app
