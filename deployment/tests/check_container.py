"""HTTPS/WSS acceptance checks against the named, disposable local test container.

Uses its dedicated volume; never imports the application or opens the local DB.
Requires backend development dependencies and Docker Desktop. Leaves the container
running for manual inspection. Self-signed TLS is test-only and added with exec,
not included in the production image. Session tokens remain in process memory.
"""
import asyncio
from contextlib import AsyncExitStack
import json
import ssl
import subprocess
import time
from uuid import uuid4

import httpx
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidStatus

CONTAINER = "signal-phase8b"
BASE = "https://localhost:18443"
SOCKET = "wss://localhost:18443/api/v1/ws"


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True, stderr=subprocess.STDOUT).strip()


def ready():
    for _ in range(100):
        try:
            with httpx.Client(base_url="http://localhost:18080", timeout=2) as c:
                if c.get("/health").status_code == 200 and c.get("/").status_code == 200:
                    return
        except httpx.HTTPError:
            pass
        time.sleep(0.3)
    raise AssertionError("Container health/frontend did not become ready")


def test_tls():
    ready()
    docker("exec", CONTAINER, "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
           "-keyout", "/tmp/test-key.pem", "-out", "/tmp/test-cert.pem", "-subj", "/CN=localhost",
           "-addext", "subjectAltName=DNS:localhost")
    code = "from pathlib import Path; p=Path('/tmp/signal-nginx.conf'); s=Path('/app/deployment/nginx.conf.template').read_text().replace('@PORT@','8080'); p.write_text(s.replace('listen 8080;', 'listen 8080; listen 8443 ssl; ssl_certificate /tmp/test-cert.pem; ssl_certificate_key /tmp/test-key.pem;'))"
    docker("exec", CONTAINER, "python", "-c", code)
    docker("exec", CONTAINER, "nginx", "-t", "-c", "/tmp/signal-nginx.conf")
    docker("exec", CONTAINER, "nginx", "-s", "reload", "-c", "/tmp/signal-nginx.conf")
    time.sleep(0.5)


def counts():
    code = "import sqlite3,json; c=sqlite3.connect('file:/data/signal.db?mode=ro',uri=True); names=['users','sessions','messages','conversations','conversation_members','message_receipts','group_creations']; print(json.dumps({n:c.execute('SELECT count(*) FROM '+n).fetchone()[0] for n in names}))"
    return json.loads(docker("exec", CONTAINER, "python", "-c", code))


async def event(ws, predicate, timeout=5):
    async def receive():
        while True:
            value = json.loads(await ws.recv())
            if predicate(value):
                return value
    return await asyncio.wait_for(receive(), timeout)


async def run():
    test_tls()
    context = ssl._create_unverified_context()  # Only the local test certificate.
    async with AsyncExitStack() as stack:
        async def login(name):
            client = await stack.enter_async_context(httpx.AsyncClient(base_url=BASE, verify=False, headers={"Origin": BASE}, timeout=10))
            response = await client.post("/api/v1/auth/verify", json={"identifier": name, "otp": "123456"})
            assert response.status_code == 200, response.text
            cookie = response.headers["set-cookie"].lower()
            assert all(flag in cookie for flag in ["httponly", "secure", "samesite=lax", "path=/"])
            assert "domain=" not in cookie
            user = response.json()["user"]
            assert (await client.get("/api/v1/auth/session")).json()["user"]["id"] == user["id"]
            return client, user

        async def ws(client, cursor=0):
            connection = await stack.enter_async_context(connect(f"{SOCKET}?cursor={cursor}", ssl=context, origin=BASE,
                additional_headers={"Cookie": f'signal_session={client.cookies.get("signal_session")}'}))
            await event(connection, lambda e: e["type"] == "session.ready")
            connection.replayed = []
            while True:
                value = json.loads(await asyncio.wait_for(connection.recv(), 5))
                if value["type"] == "sync.required":
                    break
                connection.replayed.append(value)
            return connection

        alex, a = await login("alex")
        maya, m = await login("maya")
        kai, k = await login("kai")
        new, n = await login("deploy-check-" + uuid4().hex[:12])
        assert (await new.patch("/api/v1/me", json={"display_name": "Persisted container user", "avatar_url": "/avatars/alex.jpg"})).status_code == 200
        assert (await alex.get("/health")).json() == {"status": "ok", "database": "ok"}
        page = await alex.get("/")
        assert page.status_code == 200 and "/_next/" in page.text
        assert (await alex.get("/avatars/alex.jpg")).status_code == 200
        assert (await alex.get("/openapi.json")).status_code == 200
        assert (await alex.get("/docs")).status_code == 200
        assert (await alex.get("/api/v1/auth/session", headers={"Origin": "https://wrong.example"})).status_code == 403
        preflight = await alex.options("/api/v1/auth/verify", headers={"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
        assert preflight.headers["access-control-allow-origin"] == BASE
        assert preflight.headers["access-control-allow-credentials"] == "true"
        for cookie, origin in [(None, BASE), (alex.cookies.get("signal_session"), "https://wrong.example")]:
            try:
                async with connect(SOCKET, ssl=context, origin=origin, additional_headers={"Cookie": f"signal_session={cookie}"} if cookie else {}):
                    raise AssertionError("Unauthorized socket accepted")
            except InvalidStatus:
                pass
        print("PASS: Nginx HTTPS frontend/assets/API/docs, secure cookies/session restoration, CORS/origin checks, socket authentication")
        aw, mw, kw = [await ws(c) for c in [alex, maya, kai]]
        cid = (await alex.post("/api/v1/conversations/direct", json={"contact_user_id": m["id"]})).json()["id"]

        async def send(client, conversation, text, client_id=None):
            r = await client.post(f"/api/v1/conversations/{conversation}/messages", json={"client_message_id": client_id or str(uuid4()), "body": text})
            assert r.status_code == 200, r.text
            return r.json()

        async def history(client, conversation):
            return (await client.get(f"/api/v1/conversations/{conversation}/messages")).json()["items"]

        mid = str(uuid4())
        sent = await send(alex, cid, "Container persistence hello", mid)
        assert sent["receipt"] == "sent"
        assert (await send(alex, cid, "Container persistence hello", mid))["id"] == sent["id"]
        created = await event(mw, lambda e: e["type"] == "message.created" and any(x["id"] == sent["id"] for x in e["payload"]["messages"]))
        cursor = created["event_id"]
        await event(aw, lambda e: e["type"] == "message.created" and any(x["id"] == sent["id"] for x in e["payload"]["messages"]))
        assert (await maya.get(f"/api/v1/conversations/{cid}")).json()["unread_count"] > 0
        assert (await maya.post(f"/api/v1/conversations/{cid}/delivered", json={"message_ids": [sent["id"]]})).status_code == 200
        await event(aw, lambda e: e["type"] == "message.receipt_updated" and any(x["id"] == sent["id"] and x["receipt"] == "delivered" for x in e["payload"]["messages"]))
        assert (await maya.post(f"/api/v1/conversations/{cid}/read", json={"through_sequence": sent["sequence"]})).json()["unread_count"] == 0
        await event(aw, lambda e: e["type"] == "message.receipt_updated" and any(x["id"] == sent["id"] and x["receipt"] == "read" for x in e["payload"]["messages"]))
        reply = await send(maya, cid, "Container reply")
        await event(aw, lambda e: e["type"] == "message.created" and any(x["id"] == reply["id"] for x in e["payload"]["messages"]))
        assert (await kai.get(f"/api/v1/conversations/{cid}/messages")).status_code == 403
        assert (await kai.post(f"/api/v1/conversations/{cid}/messages", json={"client_message_id": str(uuid4()), "body": "Forbidden"})).status_code == 403
        await aw.send(json.dumps({"type": "typing.started", "conversation_id": cid}))
        await event(mw, lambda e: e["type"] == "typing.updated" and e["payload"]["is_typing"])
        await event(mw, lambda e: e["type"] == "typing.updated" and not e["payload"]["is_typing"], 8)
        assert sum(x["id"] == sent["id"] for x in await history(alex, cid)) == 1
        print("PASS: bidirectional WSS messaging, deduplication, delivery/read events, persisted unread clearing, typing expiry and non-member rejection")

        group_body = {"client_group_id": str(uuid4()), "title": "Container checkpoint", "member_ids": [m["id"]]}
        group_response = await alex.post("/api/v1/groups", json=group_body)
        assert group_response.status_code == 200, group_response.text
        gid = group_response.json()["conversation"]["id"]
        assert (await alex.post("/api/v1/groups", json=group_body)).json()["conversation"]["id"] == gid
        await event(mw, lambda e: e["type"] == "group.created" and e.get("conversation_id") == gid)
        assert (await maya.patch(f"/api/v1/groups/{gid}", json={"title": "Forbidden"})).status_code == 403
        assert (await alex.post(f"/api/v1/groups/{gid}/leave")).status_code == 409
        assert (await alex.post(f"/api/v1/groups/{gid}/members", json={"member_ids": [k["id"]]})).status_code == 200
        await event(kw, lambda e: e["type"] == "group.members_updated" and e.get("conversation_id") == gid)
        group_message = await send(alex, gid, "All three through proxy")
        for connection in [mw, kw]:
            await event(connection, lambda e: e["type"] == "message.created" and any(x["id"] == group_message["id"] for x in e["payload"]["messages"]))
        for client in [maya, kai]:
            assert (await client.post(f"/api/v1/conversations/{gid}/delivered", json={"message_ids": [group_message["id"]]})).status_code == 200
            assert (await client.post(f"/api/v1/conversations/{gid}/read", json={"through_sequence": group_message["sequence"]})).json()["unread_count"] == 0
        assert next(x for x in await history(alex, gid) if x["id"] == group_message["id"])["receipt"] == "read"
        assert (await alex.delete(f'/api/v1/groups/{gid}/members/{k["id"]}')).status_code == 200
        await event(kw, lambda e: e["type"] == "conversation.access_revoked" and e.get("conversation_id") == gid)
        assert (await kai.get(f"/api/v1/conversations/{gid}/messages")).status_code == 403
        await send(alex, gid, "After removal")
        try:
            await event(kw, lambda e: e.get("conversation_id") == gid, 0.3)
            raise AssertionError("Removed member received private events")
        except asyncio.TimeoutError:
            pass
        assert (await alex.patch(f"/api/v1/groups/{gid}", json={"title": "Persisted container group"})).status_code == 200
        print("PASS: group creation/retry, permissions, add/remove, last-admin guard, group WSS messaging, aggregate read receipts and removed-member revocation")
        await mw.close()
        missed = await send(alex, cid, "Offline proxy recovery")
        mw = await ws(maya, cursor)
        assert any(e["type"] == "message.created" and any(x["id"] == missed["id"] for x in e["payload"]["messages"]) for e in mw.replayed)
        assert sum(x["id"] == missed["id"] for x in await history(maya, cid)) == 1
        pending = (await maya.get("/api/v1/messages/pending-delivery")).json()
        assert any(missed["id"] in row["message_ids"] for row in pending)
        assert (await kai.post("/api/v1/auth/logout")).status_code == 200
        try:
            await event(kw, lambda e: False)
            raise AssertionError("Logout left socket open")
        except ConnectionClosed:
            pass
        assert (await kai.get("/api/v1/auth/session")).status_code == 401
        for connection in [aw, mw]:
            await connection.close()
        before = counts()
        docker("restart", "--time", "30", CONTAINER)
        test_tls()
        assert counts() == before, "Restart/seed changed stored row counts"
        assert (await alex.get("/api/v1/auth/session")).json()["user"]["id"] == a["id"]
        assert (await maya.get("/api/v1/auth/session")).json()["user"]["id"] == m["id"]
        assert (await new.get("/api/v1/auth/session")).json()["user"]["display_name"] == "Persisted container user"
        assert (await alex.get(f"/api/v1/groups/{gid}")).json()["conversation"]["title"] == "Persisted container group"
        stored = await history(alex, cid)
        assert sum(x["id"] == missed["id"] for x in stored) == 1
        assert next(x for x in stored if x["id"] == sent["id"])["receipt"] == "read"
        assert any(x["id"] == group_message["id"] for x in await history(alex, gid))
        await ws(alex)
        await ws(maya)
        print("PASS: offline recovery, logout socket closure, graceful container restart, stable row counts, users/profiles/sessions/messages/groups/receipts and post-restart WSS")
    print("ALL CONTAINER PROTOCOL CHECKS PASSED. Browser interaction and hosted checks remain pending.")


if __name__ == "__main__":
    asyncio.run(run())
    before = counts()
    kill_backend = "from pathlib import Path; import os,signal; ids=Path('/proc/1/task/1/children').read_text().split(); pid=next(int(p) for p in ids if b'app.serve' in Path('/proc/'+p+'/cmdline').read_bytes()); os.kill(pid,signal.SIGTERM)"
    docker("exec", CONTAINER, "python", "-c", kill_backend)
    for _ in range(100):
        state = json.loads(docker("inspect", CONTAINER, "--format", "{{json .State}}"))
        if state["Status"] == "exited":
            break
        time.sleep(0.2)
    assert state["Status"] == "exited" and state["ExitCode"] == 1, state
    docker("start", CONTAINER)
    test_tls()
    assert counts() == before
    print("PASS: backend child failure stops the whole service with exit 1; restart preserves the dedicated volume")
