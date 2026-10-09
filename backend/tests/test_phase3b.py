import asyncio
import hashlib
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.database import Base, build_engine, get_db
from app.main import app
from app.models import AuthSession, Contact, Conversation, ConversationMember, DirectPair, Message, MessageReceipt, User, now_utc
from app.seed import seed_demo


@pytest.fixture
def api_db(tmp_path):
    engine = build_engine(f"sqlite:///{(tmp_path / 'api.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as db, db.begin():
        seed_demo(db)
    def override():
        with Session(engine) as db:
            yield db
    app.dependency_overrides[get_db] = override
    yield engine
    app.dependency_overrides.clear()
    engine.dispose()


def client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


async def login(c, identifier):
    challenge = await c.post("/api/v1/auth/challenges", json={"identifier": identifier})
    assert challenge.status_code == 200
    response = await c.post("/api/v1/auth/verify", json={"identifier": challenge.json()["identifier"], "otp": challenge.json()["mock_code"]})
    assert response.status_code == 200, response.text
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]
    return response.json()


def test_registration_profile_restore_and_revocation(api_db):
    async def verify():
        async with client() as c:
            assert (await c.get("/api/v1/auth/session")).status_code == 401
            for identifier in ["x", "bad name", "+123", "12345"]:
                invalid = await c.post("/api/v1/auth/challenges", json={"identifier": identifier})
                assert invalid.status_code == 422 and invalid.json()["code"] == "validation_error"
            invalid = await c.post("/api/v1/auth/verify", json={"identifier": "new-user", "otp": "000000"})
            assert invalid.status_code == 422
            session = await login(c, "NEW-USER")
            assert session["user"]["username"] == "new-user" and session["needs_profile"]
            assert (await c.get("/api/v1/auth/session")).json()["needs_profile"]
            assert (await c.patch("/api/v1/me", json={"display_name": " ", "avatar_url": "/avatars/alex.jpg"})).status_code == 422
            assert (await c.patch("/api/v1/me", json={"display_name": "New Person", "avatar_url": "javascript:bad"})).status_code == 422
            saved = await c.patch("/api/v1/me", json={"display_name": " New Person ", "avatar_url": "/avatars/alex.jpg"})
            assert saved.status_code == 200 and not saved.json()["needs_profile"]
            cookie = c.cookies.get("signal_session")
            async with client() as restored:
                restored.cookies.set("signal_session", cookie)
                assert (await restored.get("/api/v1/auth/session")).json() == saved.json()
            with Session(api_db) as db:
                row = db.scalar(select(AuthSession).where(AuthSession.user_id == session["user"]["id"]))
                assert row.token_hash == hashlib.sha256(cookie.encode()).hexdigest() and row.token_hash != cookie
                assert db.get(User, row.user_id).display_name == "New Person"
            assert (await c.post("/api/v1/auth/logout")).status_code == 200
            assert (await c.get("/api/v1/auth/session")).status_code == 401
            c.cookies.set("signal_session", cookie)
            assert (await c.get("/api/v1/auth/session")).status_code == 401
            assert not (await login(c, "new-user"))["needs_profile"]
            phone = await login(c, "+919876543210")
            assert phone["user"]["phone_e164"] == "+919876543210" and phone["user"]["username"] is None
    asyncio.run(verify())


def test_scoped_contacts_add_search_and_errors(api_db):
    async def verify():
        async with client() as alex, client() as newcomer:
            a = (await login(alex, "alex"))["user"]
            n = (await login(newcomer, "new-contact"))["user"]
            assert (await newcomer.get("/api/v1/contacts")).json() == []
            assert len((await alex.get("/api/v1/contacts")).json()) == 5
            searched = (await alex.get("/api/v1/contacts?query=MAYA")).json()
            assert len(searched) == 1 and searched[0]["user"]["username"] == "maya"
            assert (await alex.get("/api/v1/contacts?query=%25")).json() == []
            found = (await newcomer.get("/api/v1/users?query=Alex")).json()
            assert found[0]["id"] == a["id"]
            added = await newcomer.post("/api/v1/contacts", json={"contact_user_id": a["id"], "alias": "My Alex"})
            assert added.status_code == 201
            assert (await newcomer.get("/api/v1/contacts?query=My%20Alex")).json()[0]["alias"] == "My Alex"
            assert (await newcomer.post("/api/v1/contacts", json={"contact_user_id": a["id"]})).status_code == 409
            assert (await newcomer.post("/api/v1/contacts", json={"contact_user_id": n["id"]})).status_code == 422
            assert (await newcomer.post("/api/v1/contacts", json={"contact_user_id": "missing"})).status_code == 404
            assert len((await alex.get("/api/v1/contacts")).json()) == 5  # directional
            rejected = await alex.post("/api/v1/auth/logout", headers={"Origin": "http://untrusted.example"})
            assert rejected.status_code == 403
            assert (await alex.get("/api/v1/auth/session")).status_code == 200
    asyncio.run(verify())


def test_inbox_history_membership_unread_and_receipts(api_db):
    async def verify():
        async with client() as alex, client() as maya, client() as sam:
            a = (await login(alex, "alex"))["user"]
            await login(maya, "maya"); await login(sam, "sam")
            inbox = (await alex.get("/api/v1/conversations")).json()
            assert len(inbox) == 5 and len((await maya.get("/api/v1/conversations")).json()) == 3
            assert len((await sam.get("/api/v1/conversations")).json()) == 1
            assert [c["last_activity_at"] for c in inbox] == sorted([c["last_activity_at"] for c in inbox], reverse=True)
            for conversation in inbox:
                response = await alex.get(f'/api/v1/conversations/{conversation["id"]}/messages?limit=2')
                assert response.status_code == 200
                page = response.json(); messages = page["items"]
                while page["next_cursor"]:
                    page = (await alex.get(f'/api/v1/conversations/{conversation["id"]}/messages', params={"limit": 2, "before_sequence": page["next_cursor"]})).json()
                    messages = page["items"] + messages
                sequences = [m["sequence"] for m in messages]
                assert sequences == sorted(set(sequences)) and len(messages) == (6 if conversation["kind"] == "group" else 7)
                with Session(api_db) as db:
                    member = db.get(ConversationMember, (conversation["id"], a["id"]))
                    expected = db.scalar(select(func.count()).select_from(Message).join(MessageReceipt, MessageReceipt.message_id == Message.id).where(Message.conversation_id == conversation["id"], Message.sender_id != a["id"], Message.sequence > member.last_read_sequence, MessageReceipt.recipient_user_id == a["id"]))
                    assert conversation["unread_count"] == expected
                    for m in messages:
                        assert m["sender"]["display_name"]
                        if m["sender"]["id"] != a["id"]:
                            assert m["receipt"] is None
                        else:
                            receipts = db.scalars(select(MessageReceipt).where(MessageReceipt.message_id == m["id"])).all()
                            expected_receipt = "read" if all(r.read_at for r in receipts) else "delivered" if all(r.delivered_at for r in receipts) else "sent"
                            assert m["receipt"] == expected_receipt
                if conversation["title"] != "Weekend plans":
                    denied = await sam.get(f'/api/v1/conversations/{conversation["id"]}/messages')
                    assert denied.status_code == 403 and denied.json()["code"] == "forbidden"
            assert (await alex.get("/api/v1/conversations/missing/messages")).status_code == 404
            assert (await alex.get(f'/api/v1/conversations/{inbox[0]["id"]}/messages?limit=101')).status_code == 422
    asyncio.run(verify())


def test_direct_creation_reopen_concurrent_and_empty(api_db):
    async def verify():
        async with client() as alex, client() as julian:
            a = (await login(alex, "alex"))["user"]
            j = (await login(julian, "julian"))["user"]
            # Parallel repeated requests on a previously absent pair.
            responses = await asyncio.gather(*[alex.post("/api/v1/conversations/direct", json={"contact_user_id": j["id"]}) for _ in range(8)])
            assert all(r.status_code == 200 for r in responses), [r.text for r in responses]
            ids = {r.json()["id"] for r in responses}; assert len(ids) == 1
            cid = ids.pop()
            reverse = await julian.post("/api/v1/conversations/direct", json={"contact_user_id": a["id"]})
            assert reverse.json()["id"] == cid
            assert (await alex.get(f"/api/v1/conversations/{cid}/messages")).json() == {"items": [], "next_cursor": None}
            assert reverse.json()["latest_message"] is None and reverse.json()["unread_count"] == 0
            assert any(c["id"] == cid for c in (await julian.get("/api/v1/conversations")).json())
            with Session(api_db) as db:
                assert db.scalar(select(func.count()).select_from(Conversation)) == 7
                assert db.scalar(select(func.count()).select_from(DirectPair)) == 5
                assert db.scalar(select(func.count()).select_from(ConversationMember).where(ConversationMember.conversation_id == cid)) == 2
    asyncio.run(verify())


def test_expired_session_and_database_failure(api_db):
    async def verify():
        async with client() as c:
            user = (await login(c, "alex"))["user"]
            with Session(api_db) as db, db.begin():
                session = db.scalar(select(AuthSession).where(AuthSession.user_id == user["id"]))
                session.created_at = now_utc() - timedelta(days=2)
                session.expires_at = now_utc() - timedelta(days=1)
            assert (await c.get("/api/v1/conversations")).status_code == 401
            def unavailable():
                raise OperationalError("unavailable", {}, Exception("offline"))
                yield  # dependency generator
            app.dependency_overrides[get_db] = unavailable
            failed = await c.get("/api/v1/auth/session")
            assert failed.status_code == 503 and failed.json()["code"] == "unavailable"
            assert "user" not in failed.json()
    asyncio.run(verify())
