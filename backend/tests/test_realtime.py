"""Real HTTP/WebSocket protocol against an isolated SQLite database and server."""
import asyncio
import socket
import threading
import time
from contextlib import AsyncExitStack
from uuid import uuid4

import httpx
import pytest
import uvicorn
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidStatus

from app.database import Base, build_engine, get_db
from app.main import app
from app.models import Message, MessageReceipt, User
from app.realtime import manager
from app.seed import seed_demo


@pytest.fixture
def live_server(tmp_path):
    engine = build_engine(f"sqlite:///{(tmp_path / 'realtime.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as db, db.begin():
        seed_demo(db)
    def override():
        with Session(engine) as db:
            yield db
    app.dependency_overrides[get_db] = override
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    for _ in range(200):
        if server.started:
            break
        time.sleep(.05)
    assert server.started
    yield f"http://127.0.0.1:{port}", f"ws://127.0.0.1:{port}/api/v1/ws", engine
    server.should_exit = True
    thread.join(10)
    assert not thread.is_alive()
    app.dependency_overrides.clear()
    manager.connections.clear()
    manager.typing.clear()
    engine.dispose()


async def event(ws, predicate, timeout=3):
    import json
    async def receive():
        while True:
            value = json.loads(await ws.recv())
            if predicate(value):
                return value
    return await asyncio.wait_for(receive(), timeout)


def test_authenticated_realtime_receipts_recovery_and_logout(live_server):
    base, ws_url, engine = live_server
    origin = "http://localhost:3000"
    async def verify():
        async with AsyncExitStack() as stack:
            async def login(name):
                c = await stack.enter_async_context(httpx.AsyncClient(base_url=base, headers={"Origin": origin}, timeout=10))
                challenge = (await c.post("/api/v1/auth/challenges", json={"identifier": name})).json()
                response = await c.post("/api/v1/auth/verify", json={"identifier": name, "otp": challenge["mock_code"]})
                assert response.status_code == 200
                return c, response.json()["user"]
            alex, a = await login("alex")
            other, _ = await login("alex")
            maya, m = await login("maya")
            kai, k = await login("kai")
            sam, s = await login("sam")
            async def open_ws(c, cursor=0):
                ws = await stack.enter_async_context(connect(f"{ws_url}?cursor={cursor}", origin=origin, additional_headers={"Cookie": f'signal_session={c.cookies.get("signal_session")}'}))
                ready = await event(ws, lambda e: e["type"] == "session.ready")
                assert ready["payload"]["user_id"]
                return ws
            for headers, bad_origin in [({}, origin), ({"Cookie": f'signal_session={alex.cookies.get("signal_session")}'}, "http://untrusted.example")]:
                with pytest.raises(InvalidStatus):
                    async with connect(ws_url, origin=bad_origin, additional_headers=headers):
                        pass
            aw, ow, mw, kw, sw = [await open_ws(c) for c in [alex, other, maya, kai, sam]]
            for ws in [aw, ow, mw, kw, sw]:
                await event(ws, lambda e: e["type"] == "sync.required")
            direct = (await alex.post("/api/v1/conversations/direct", json={"contact_user_id": m["id"]})).json()
            cid = direct["id"]
            original_unread = direct["unread_count"]
            group = next(c for c in (await alex.get("/api/v1/conversations")).json() if c["title"] == "Roommates")
            gid = group["id"]
            async def send(c, conversation_id, text, client_id=None):
                result = await c.post(f"/api/v1/conversations/{conversation_id}/messages", json={"client_message_id": client_id or str(uuid4()), "body": text})
                assert result.status_code == 200, result.text
                return result.json()
            client_id = str(uuid4())
            sent = await send(alex, cid, "Persistent hello", client_id)
            assert sent["receipt"] == "sent" and sent["sender"]["id"] == a["id"]
            assert (await alex.get(f"/api/v1/conversations/{cid}")).json()["unread_count"] == original_unread
            for ws in [aw, ow, mw]:
                created = await event(ws, lambda e: e["type"] == "message.created" and e["payload"]["messages"][0]["id"] == sent["id"])
                assert created["payload"]["conversation"]["id"] == cid
            with pytest.raises(asyncio.TimeoutError):
                await event(sw, lambda e: e.get("conversation_id") == cid and e["type"] == "message.created", .2)
            duplicates = await asyncio.gather(*[send(alex, cid, "Persistent hello", client_id) for _ in range(6)])
            assert {r["id"] for r in duplicates} == {sent["id"]}
            mismatch = await alex.post(f"/api/v1/conversations/{cid}/messages", json={"client_message_id": client_id, "body": "Different"})
            assert mismatch.status_code == 409
            for bad in ["   ", "x" * 4001]:
                assert (await alex.post(f"/api/v1/conversations/{cid}/messages", json={"client_message_id": str(uuid4()), "body": bad})).status_code == 422
            assert (await alex.post(f"/api/v1/conversations/{cid}/messages", json={"client_message_id": str(uuid4()), "body": "Spoof", "sender_id": m["id"]})).status_code == 422
            for endpoint, body in [("messages", {"client_message_id": str(uuid4()), "body": "Unauthorized"}), ("delivered", {"message_ids": [sent["id"]]}), ("read", {"through_sequence": sent["sequence"]})]:
                assert (await sam.post(f"/api/v1/conversations/{cid}/{endpoint}", json=body)).status_code == 403
            await sw.send(__import__('json').dumps({"type": "message.delivered", "conversation_id": cid, "message_ids": [sent["id"]]}))
            assert (await event(sw, lambda e: e["type"] == "error"))["payload"]["code"] == "forbidden"
            await aw.send(__import__('json').dumps({"type": "message.delivered", "conversation_id": cid, "message_ids": [sent["id"]]}))
            assert (await event(aw, lambda e: e["type"] == "error"))["payload"]["code"] == "forbidden"
            await mw.send(__import__('json').dumps({"type": "message.delivered", "conversation_id": cid, "message_ids": [sent["id"]]}))
            delivered = await event(aw, lambda e: e["type"] == "message.receipt_updated" and any(x["id"] == sent["id"] and x["receipt"] == "delivered" for x in e["payload"]["messages"]))
            assert delivered
            with Session(engine) as db:
                receipt = db.get(MessageReceipt, (sent["id"], m["id"]))
                assert receipt.delivered_at is not None and receipt.read_at is None
            await mw.send(__import__('json').dumps({"type": "conversation.read", "conversation_id": cid, "through_sequence": sent["sequence"]}))
            await event(aw, lambda e: e["type"] == "message.receipt_updated" and any(x["id"] == sent["id"] and x["receipt"] == "read" for x in e["payload"]["messages"]))
            read_event = await event(mw, lambda e: e["type"] == "message.receipt_updated" and e["payload"]["conversation"]["id"] == cid and e["payload"]["conversation"]["unread_count"] == 0)
            await maya.post(f"/api/v1/conversations/{cid}/delivered", json={"message_ids": [sent["id"]]})
            with Session(engine) as db:
                receipt = db.get(MessageReceipt, (sent["id"], m["id"]))
                before = (receipt.delivered_at, receipt.read_at)
                assert db.scalar(select(func.count()).select_from(Message).where(Message.sender_id == a["id"], Message.client_message_id == client_id)) == 1
            assert (await maya.post(f"/api/v1/conversations/{cid}/read", json={"through_sequence": sent["sequence"]})).json()["unread_count"] == 0
            with Session(engine) as db:
                receipt = db.get(MessageReceipt, (sent["id"], m["id"]))
                assert (receipt.delivered_at, receipt.read_at) == before
            reply = await send(maya, cid, "Maya replies through the same direct chat")
            for ws in [aw, ow]:
                await event(ws, lambda e: e["type"] == "message.created" and any(x["id"] == reply["id"] for x in e["payload"]["messages"]))
            assert (await maya.get(f"/api/v1/conversations/{cid}")).json()["unread_count"] == 0
            await alex.post(f"/api/v1/conversations/{cid}/delivered", json={"message_ids": [reply["id"]]})
            await event(mw, lambda e: e["type"] == "message.receipt_updated" and any(x["id"] == reply["id"] and x["receipt"] == "delivered" for x in e["payload"]["messages"]))
            await alex.post(f"/api/v1/conversations/{cid}/read", json={"through_sequence": reply["sequence"]})
            await event(mw, lambda e: e["type"] == "message.receipt_updated" and any(x["id"] == reply["id"] and x["receipt"] == "read" for x in e["payload"]["messages"]))
            group_message = await send(alex, gid, "Hello Roommates")
            for ws in [mw, kw]:
                await event(ws, lambda e: e["type"] == "message.created" and e.get("conversation_id") == gid)
            with pytest.raises(asyncio.TimeoutError):
                await event(sw, lambda e: e["type"] == "message.created" and e.get("conversation_id") == gid, .2)
            await maya.post(f"/api/v1/conversations/{gid}/read", json={"through_sequence": group_message["sequence"]})
            current = (await alex.get(f"/api/v1/conversations/{gid}/messages")).json()["items"][-1]
            assert current["receipt"] == "sent"  # Kai has not acknowledged anything.
            await kai.post(f"/api/v1/conversations/{gid}/delivered", json={"message_ids": [group_message["id"]]})
            assert (await alex.get(f"/api/v1/conversations/{gid}/messages")).json()["items"][-1]["receipt"] == "delivered"
            await kai.post(f"/api/v1/conversations/{gid}/read", json={"through_sequence": group_message["sequence"]})
            assert (await alex.get(f"/api/v1/conversations/{gid}/messages")).json()["items"][-1]["receipt"] == "read"
            assert (await maya.post(f"/api/v1/conversations/{cid}/read", json={"through_sequence": group_message["sequence"]})).status_code == 422
            await aw.send(__import__('json').dumps({"type": "typing.started", "conversation_id": cid}))
            await event(mw, lambda e: e["type"] == "typing.updated" and e["payload"]["is_typing"])
            await event(mw, lambda e: e["type"] == "typing.updated" and not e["payload"]["is_typing"], 7)
            new_direct = (await alex.post("/api/v1/conversations/direct", json={"contact_user_id": s["id"]})).json()
            await event(sw, lambda e: e["type"] == "conversation.updated" and e.get("conversation_id") == new_direct["id"])
            # Recipient offline: sending persists but cannot manufacture delivery.
            await mw.close()
            missed = await send(alex, cid, "While Maya is offline")
            assert missed["receipt"] == "sent"
            fresh = await open_ws(maya, read_event["event_id"])
            replayed = await event(fresh, lambda e: e["type"] == "message.created" and any(x["id"] == missed["id"] for x in e["payload"]["messages"]))
            assert replayed["event_id"] > read_event["event_id"]
            await event(fresh, lambda e: e["type"] == "sync.required")
            history = (await maya.get(f"/api/v1/conversations/{cid}/messages")).json()["items"]
            assert sum(x["id"] == missed["id"] for x in history) == 1
            assert [x["sequence"] for x in history] == sorted(x["sequence"] for x in history)
            recovery = (await maya.get("/api/v1/messages/pending-delivery")).json()
            assert any(missed["id"] in row["message_ids"] for row in recovery)
            for row in recovery:
                assert (await maya.post(f'/api/v1/conversations/{row["conversation_id"]}/delivered', json={"message_ids": row["message_ids"]})).status_code == 200
            await maya.post(f"/api/v1/conversations/{cid}/read", json={"through_sequence": missed["sequence"]})
            assert (await maya.get(f"/api/v1/conversations/{cid}")).json()["unread_count"] == 0
            await alex.post(f"/api/v1/conversations/{cid}/read", json={"through_sequence": missed["sequence"]})
            assert (await alex.get(f"/api/v1/conversations/{cid}")).json()["unread_count"] == 0
            # Other Alex session keeps him online until his final socket closes.
            assert (await maya.get(f"/api/v1/conversations/{cid}")).json()["other_user"]["online"]
            await ow.close()
            assert (await maya.get(f"/api/v1/conversations/{cid}")).json()["other_user"]["online"]
            await aw.close()
            await event(fresh, lambda e: e["type"] == "presence.updated" and e["payload"]["user_id"] == a["id"] and not e["payload"]["online"])
            with Session(engine) as db:
                assert db.get(User, a["id"]).last_seen_at is not None
            old_cookie = maya.cookies.get("signal_session")
            assert (await maya.post("/api/v1/auth/logout")).status_code == 200
            with pytest.raises(ConnectionClosed):
                await event(fresh, lambda e: False)
            with pytest.raises(InvalidStatus):
                async with connect(ws_url, origin=origin, additional_headers={"Cookie": f"signal_session={old_cookie}"}):
                    pass
    asyncio.run(verify())
