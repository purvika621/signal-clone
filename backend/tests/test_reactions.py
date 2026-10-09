import asyncio
from contextlib import AsyncExitStack
from uuid import uuid4

import httpx
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from websockets.asyncio.client import connect

from app.models import MessageReaction, UserEvent
from test_realtime import live_server, event


def test_reactions_persist_idempotent_authorized_and_realtime(live_server):
    base, socket_url, engine = live_server
    origin = "http://localhost:3000"
    async def verify():
        async with AsyncExitStack() as stack:
            async def login(name):
                c = await stack.enter_async_context(httpx.AsyncClient(base_url=base, headers={"Origin": origin}))
                response = await c.post("/api/v1/auth/verify", json={"identifier": name, "otp": "123456"})
                assert response.status_code == 200
                return c, response.json()["user"]
            alex, a = await login("alex")
            maya, m = await login("maya")
            kai, k = await login("kai")
            ws = await stack.enter_async_context(connect(socket_url, origin=origin,
                additional_headers={"Cookie": f'signal_session={maya.cookies.get("signal_session")}'}))
            await event(ws, lambda e: e["type"] == "sync.required")
            cid = (await alex.post("/api/v1/conversations/direct", json={"contact_user_id": m["id"]})).json()["id"]
            sent = await alex.post(f"/api/v1/conversations/{cid}/messages", json={"client_message_id": str(uuid4()), "body": "React here"})
            assert sent.status_code == 200
            mid = sent.json()["id"]
            path = f"/api/v1/conversations/{cid}/messages/{mid}/reactions"
            result = await alex.post(path, json={"emoji": "👍", "active": True})
            assert result.status_code == 200, result.text
            assert result.json()["reaction_version"] == 1
            frame = await event(ws, lambda e: e["type"] == "message.reactions_updated")
            assert frame["payload"]["messages"][0]["reactions"] == [{"user_id": a["id"], "emoji": "👍"}]
            repeat = await alex.post(path, json={"emoji": "👍", "active": True})
            assert repeat.json()["reaction_version"] == 1
            both = await maya.post(path, json={"emoji": "👍", "active": True})
            assert len(both.json()["reactions"]) == 2
            assert (await kai.post(path, json={"emoji": "👍", "active": True})).status_code == 403
            assert (await alex.post(path, json={"emoji": "invalid", "active": True})).status_code == 422
            assert (await alex.post(path, json={"emoji": "👍", "active": True, "user_id": k["id"]})).status_code == 422
            removed = await alex.post(path, json={"emoji": "👍", "active": False})
            assert removed.json()["reactions"] == [{"user_id": m["id"], "emoji": "👍"}]
            assert (await alex.post(path, json={"emoji": "👍", "active": False})).json()["reaction_version"] == 3
            history = (await maya.get(f"/api/v1/conversations/{cid}/messages")).json()["items"]
            assert next(msg for msg in history if msg["id"] == mid)["reactions"] == removed.json()["reactions"]
            group = (await alex.post("/api/v1/groups", json={"client_group_id": str(uuid4()), "title": "Reaction test", "member_ids": [m["id"], k["id"]]})).json()
            gid = group["conversation"]["id"]
            group_message = (await kai.post(f"/api/v1/conversations/{gid}/messages", json={"client_message_id": str(uuid4()), "body": "Group reaction"})).json()
            gp = f'/api/v1/conversations/{gid}/messages/{group_message["id"]}/reactions'
            assert (await maya.post(gp, json={"emoji": "❤️", "active": True})).status_code == 200
            assert (await alex.post(f"/api/v1/conversations/{gid}/messages/{mid}/reactions", json={"emoji": "👍", "active": True})).status_code == 404
            assert (await alex.delete(f'/api/v1/groups/{gid}/members/{m["id"]}')).status_code == 200
            assert (await maya.post(gp, json={"emoji": "🎉", "active": True})).status_code == 403
            with Session(engine) as db:
                assert db.scalar(select(func.count()).select_from(MessageReaction).where(MessageReaction.message_id == mid)) == 1
                assert db.scalar(select(func.count()).select_from(UserEvent).where(UserEvent.user_id == k["id"], UserEvent.type == "message.reactions_updated", UserEvent.payload_json["conversation_id"].as_string() == cid)) == 0
    asyncio.run(verify())


def test_reaction_migration_is_repeatable_and_preserves_old_data(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from app import database
    from app.config import BACKEND_DIR
    engine = database.build_engine(f"sqlite:///{(tmp_path / 'migration.db').as_posix()}")
    monkeypatch.setattr(database, "engine", engine)
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    command.upgrade(config, "0003")
    with engine.begin() as db:
        db.execute(text("INSERT INTO users (id,username,display_name,created_at) VALUES ('u','legacy','Legacy','2026-10-09 00:00:00')"))
        db.execute(text("INSERT INTO conversations (id,kind,title,created_by,created_at,last_activity_at) VALUES ('c','group','Preserved','u','2026-10-09 00:00:00','2026-10-09 00:00:00')"))
        db.execute(text("INSERT INTO messages (id,conversation_id,sender_id,client_message_id,kind,body,created_at) VALUES ('m','c','u','client','text','Preserve me','2026-10-09 00:00:00')"))
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    command.check(config)
    with engine.connect() as db:
        assert db.execute(text("SELECT body, reaction_version FROM messages WHERE id='m'")).one() == ("Preserve me", 0)
        assert db.scalar(text("SELECT title FROM conversations WHERE id='c'")) == "Preserved"
        assert db.scalar(text("SELECT COUNT(*) FROM message_reactions")) == 0
    engine.dispose()
