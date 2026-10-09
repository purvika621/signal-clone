"""Group authorization and revocation over real HTTP/WebSocket connections."""
import asyncio
import json
from contextlib import AsyncExitStack
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from websockets.asyncio.client import connect

from app.models import Conversation, ConversationMember, GroupCreation, Message, MessageReceipt
from app.realtime import Connection, ConnectionManager
from test_realtime import live_server, event


def test_removal_discards_queued_frames_and_stale_typing_audience():
    async def verify():
        manager = ConnectionManager()
        removed = Connection(None, "removed", "s1", "Removed")
        remaining = Connection(None, "remaining", "s2", "Remaining")
        manager.connections.update([removed, remaining])
        manager.enqueue(removed, {"type": "message.created", "conversation_id": "group"})
        manager.enqueue(removed, {"type": "pong"})
        manager.set_typing(remaining, "group", ["removed"], True)
        manager.membership_changed("group", removed=["removed"])
        assert removed.queue.qsize() == 1
        assert removed.queue.get_nowait()["type"] == "pong"
        assert manager.typing[(remaining, "group")]["recipients"] == []
        manager.emit(["removed"], {"type": "message.created", "conversation_id": "group"})
        assert removed.queue.empty()
        manager.emit(["removed"], {"type": "conversation.access_revoked", "conversation_id": "group"})
        assert removed.queue.get_nowait()["type"] == "conversation.access_revoked"
        manager.membership_changed("group", added=["removed"])
        manager.emit(["removed"], {"type": "message.created", "conversation_id": "group"})
        assert removed.queue.get_nowait()["type"] == "message.created"
    asyncio.run(verify())


def test_group_lifecycle_permissions_and_realtime(live_server):
    base, ws_url, engine = live_server
    origin = "http://localhost:3000"
    async def verify():
        async with AsyncExitStack() as stack:
            async def login(name):
                client = await stack.enter_async_context(httpx.AsyncClient(base_url=base, headers={"Origin": origin}))
                result = await client.post("/api/v1/auth/verify", json={"identifier": name, "otp": "123456"})
                assert result.status_code == 200
                return client, result.json()["user"]
            alex, a = await login("alex")
            maya, m = await login("maya")
            kai, k = await login("kai")
            async def ws(client, cursor=0):
                connection = await stack.enter_async_context(connect(f"{ws_url}?cursor={cursor}", origin=origin,
                    additional_headers={"Cookie": f'signal_session={client.cookies.get("signal_session")}'}))
                await event(connection, lambda e: e["type"] == "session.ready")
                return connection
            aw, mw, kw = [await ws(c) for c in [alex, maya, kai]]
            for connection in [aw, mw, kw]:
                await event(connection, lambda e: e["type"] == "sync.required")
            body = {"client_group_id": str(uuid4()), "title": "Checkpoint group", "member_ids": [m["id"]]}
            for invalid in [{**body, "title": "   "}, {**body, "member_ids": []}, {**body, "member_ids": [m["id"], m["id"]]}, {**body, "member_ids": [a["id"]]}, {**body, "member_ids": [str(uuid4())]}]:
                assert (await alex.post("/api/v1/groups", json=invalid)).status_code == 422
            replies = await asyncio.gather(*[alex.post("/api/v1/groups", json=body) for _ in range(5)])
            assert all(r.status_code == 200 for r in replies), [r.text for r in replies]
            gid = replies[0].json()["conversation"]["id"]
            assert {r.json()["conversation"]["id"] for r in replies} == {gid}
            assert replies[0].json()["my_role"] == "admin"
            for connection in [aw, mw]:
                await event(connection, lambda e: e["type"] == "group.created" and e.get("conversation_id") == gid)
            assert (await alex.post("/api/v1/groups", json={**body, "title": "different"})).status_code == 409
            with Session(engine) as db:
                assert db.scalar(select(func.count()).select_from(Conversation).where(Conversation.title == body["title"])) == 1
                assert db.scalar(select(func.count()).select_from(GroupCreation).where(GroupCreation.conversation_id == gid)) == 1
                assert db.get(ConversationMember, (gid, a["id"])).role == "admin"
                assert db.get(ConversationMember, (gid, m["id"])).role == "member"
            assert (await maya.get(f"/api/v1/groups/{gid}/members")).status_code == 200
            assert (await kai.get(f"/api/v1/groups/{gid}")).status_code == 403
            for method, endpoint, payload in [("post", "/members", {"member_ids": [k["id"]]}), ("patch", "", {"title": "spoof"}), ("patch", f'/members/{a["id"]}', {"role": "member"}), ("delete", f'/members/{a["id"]}', None)]:
                assert (await maya.request(method, f"/api/v1/groups/{gid}{endpoint}", **({"json": payload} if payload else {}))).status_code == 403
            assert (await alex.post(f"/api/v1/groups/{gid}/leave")).status_code == 409
            assert (await alex.patch(f'/api/v1/groups/{gid}/members/{a["id"]}', json={"role": "member"})).status_code == 409
            async def send(client, text):
                response = await client.post(f"/api/v1/conversations/{gid}/messages", json={"client_message_id": str(uuid4()), "body": text})
                assert response.status_code == 200, response.text
                return response.json()
            first = await send(alex, "Before Kai joins")
            created = await event(mw, lambda e: e["type"] == "message.created" and e.get("conversation_id") == gid)
            cursor = created["event_id"]
            assert created["payload"]["conversation"]["unread_count"] == 1
            assert (await maya.post(f"/api/v1/conversations/{gid}/read", json={"through_sequence": first["sequence"]})).json()["unread_count"] == 0
            assert (await alex.post(f"/api/v1/groups/{gid}/members", json={"member_ids": [k["id"]]})).status_code == 200
            added = await event(kw, lambda e: e["type"] == "group.members_updated" and e.get("conversation_id") == gid)
            assert added["payload"]["conversation"]["unread_count"] == 0
            assert (await alex.post(f"/api/v1/groups/{gid}/members", json={"member_ids": [k["id"]]})).status_code == 409
            history = (await kai.get(f"/api/v1/conversations/{gid}/messages")).json()["items"]
            assert any(msg["id"] == first["id"] for msg in history)  # Full pre-join history is allowed.
            with Session(engine) as db:
                assert db.get(MessageReceipt, (first["id"], k["id"])) is None
            second = await send(alex, "All three members")
            for connection in [mw, kw]:
                await event(connection, lambda e: e["type"] == "message.created" and any(msg["id"] == second["id"] for msg in e["payload"]["messages"]))
            for client in [maya, kai]:
                assert (await client.post(f"/api/v1/conversations/{gid}/delivered", json={"message_ids": [second["id"]]})).status_code == 200
            assert next(msg for msg in (await alex.get(f"/api/v1/conversations/{gid}/messages")).json()["items"] if msg["id"] == second["id"])["receipt"] == "delivered"
            for client in [maya, kai]:
                assert (await client.post(f"/api/v1/conversations/{gid}/read", json={"through_sequence": second["sequence"]})).json()["unread_count"] == 0
            assert next(msg for msg in (await alex.get(f"/api/v1/conversations/{gid}/messages")).json()["items"] if msg["id"] == second["id"])["receipt"] == "read"
            await mw.send(json.dumps({"type": "typing.started", "conversation_id": gid}))
            await event(kw, lambda e: e["type"] == "typing.updated" and e.get("conversation_id") == gid and e["payload"]["is_typing"])
            # Removing an actively typing member stops the indicator on remaining clients.
            assert (await alex.delete(f'/api/v1/groups/{gid}/members/{m["id"]}')).status_code == 200
            await event(mw, lambda e: e["type"] == "conversation.access_revoked" and e.get("conversation_id") == gid)
            await event(kw, lambda e: e["type"] == "typing.updated" and e.get("conversation_id") == gid and not e["payload"]["is_typing"])
            with Session(engine) as db:
                assert db.get(ConversationMember, (gid, m["id"])).left_at is not None
                assert db.get(MessageReceipt, (first["id"], m["id"])).read_at is not None
                assert db.get(MessageReceipt, (second["id"], m["id"])).read_at is not None
            for endpoint in [f"/groups/{gid}", f"/groups/{gid}/members", f"/conversations/{gid}/messages"]:
                assert (await maya.get(f"/api/v1{endpoint}")).status_code == 403
            assert all(c["id"] != gid for c in (await maya.get("/api/v1/conversations")).json())
            for endpoint, payload in [("messages", {"client_message_id": str(uuid4()), "body": "stale client"}), ("delivered", {"message_ids": [second["id"]]}), ("read", {"through_sequence": second["sequence"]})]:
                assert (await maya.post(f"/api/v1/conversations/{gid}/{endpoint}", json=payload)).status_code == 403
            await mw.send(json.dumps({"type": "typing.started", "conversation_id": gid}))
            assert (await event(mw, lambda e: e["type"] == "error"))["payload"]["code"] == "forbidden"
            third = await send(kai, "After Maya removal")
            await aw.send(json.dumps({"type": "typing.started", "conversation_id": gid}))
            await event(kw, lambda e: e["type"] == "typing.updated" and e.get("conversation_id") == gid and e["payload"]["is_typing"])
            with pytest.raises(asyncio.TimeoutError):
                await event(mw, lambda e: e.get("conversation_id") == gid, .3)
            # Reconnect must replay revocation, never private messages after removal.
            await mw.close()
            fresh = await ws(maya, cursor)
            await event(fresh, lambda e: e["type"] == "conversation.access_revoked" and e.get("conversation_id") == gid)
            await event(fresh, lambda e: e["type"] == "sync.required")
            with pytest.raises(asyncio.TimeoutError):
                await event(fresh, lambda e: e["type"] == "message.created" and e.get("conversation_id") == gid, .2)
            assert (await alex.patch(f"/api/v1/groups/{gid}", json={"title": "Renamed checkpoint"})).status_code == 200
            assert (await alex.get(f"/api/v1/groups/{gid}")).json()["conversation"]["title"] == "Renamed checkpoint"
            # Retry original intent even after edits still returns the original group.
            assert (await alex.post("/api/v1/groups", json=body)).json()["conversation"]["id"] == gid
            assert (await alex.patch(f'/api/v1/groups/{gid}/members/{k["id"]}', json={"role": "admin"})).status_code == 200
            assert (await alex.post(f"/api/v1/groups/{gid}/leave")).status_code == 200
            await event(aw, lambda e: e["type"] == "conversation.access_revoked" and e.get("conversation_id") == gid)
            assert (await kai.post(f"/api/v1/groups/{gid}/leave")).status_code == 409
            assert (await kai.post(f"/api/v1/groups/{gid}/members", json={"member_ids": [m["id"]]})).status_code == 200
            await event(fresh, lambda e: e["type"] == "group.members_updated" and e.get("conversation_id") == gid)
            rejoined = (await maya.get(f"/api/v1/groups/{gid}")).json()
            assert rejoined["my_role"] == "member" and rejoined["conversation"]["unread_count"] == 0
            fourth = await send(kai, "Welcome back Maya")
            await event(fresh, lambda e: e["type"] == "message.created" and any(msg["id"] == fourth["id"] for msg in e["payload"]["messages"]))
            assert (await maya.post(f"/api/v1/groups/{gid}/leave")).status_code == 200
            assert (await maya.get(f"/api/v1/groups/{gid}")).status_code == 403
            # Existing direct messaging remains independent of group membership.
            direct = (await alex.post("/api/v1/conversations/direct", json={"contact_user_id": m["id"]})).json()["id"]
            assert (await alex.post(f"/api/v1/conversations/{direct}/messages", json={"client_message_id": str(uuid4()), "body": "Direct still works"})).status_code == 200
            await event(fresh, lambda e: e["type"] == "message.created" and e.get("conversation_id") == direct)
            with Session(engine) as db:
                assert db.get(MessageReceipt, (third["id"], m["id"])) is None
                assert db.scalar(select(func.count()).select_from(Message).where(Message.conversation_id == gid, Message.kind == "text")) == 4
                assert db.get(ConversationMember, (gid, k["id"])).role == "admin"
    asyncio.run(verify())
