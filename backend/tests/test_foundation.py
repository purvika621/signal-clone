import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, configure_mappers

from app.database import Base, build_engine, get_db
from app.main import app
from app.models import Contact, Conversation, ConversationMember, DirectPair, Message, MessageReceipt, User
from app.seed import seed_demo


@pytest.fixture
def db_engine(tmp_path):
    engine = build_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def test_schema_and_pragmas(db_engine):
    configure_mappers()
    assert set(inspect(db_engine).get_table_names()) == set(Base.metadata.tables)
    with db_engine.connect() as db:
        assert db.scalar(text("PRAGMA foreign_keys")) == 1
        assert db.scalar(text("PRAGMA journal_mode")) == "wal"
        assert db.scalar(text("PRAGMA busy_timeout")) == 5000


def test_seed_is_repeatable_and_preserves_edits(db_engine):
    with Session(db_engine) as db, db.begin():
        seed_demo(db)
    with Session(db_engine) as db, db.begin():
        user = db.scalars(select(User)).first()
        user.display_name = "Edited locally"
        message = db.scalars(select(Message)).first()
        message.body = "Preserve this edit"
        member = db.scalars(select(ConversationMember)).first()
        member.last_read_sequence = 0
        snapshot = (user.id, message.id, member.conversation_id, member.user_id)
    with db_engine.connect() as db:
        before = {t: db.scalar(text(f'SELECT COUNT(*) FROM "{t}"')) for t in Base.metadata.tables}
    with Session(db_engine) as db, db.begin():
        seed_demo(db)
    with db_engine.connect() as db:
        after = {t: db.scalar(text(f'SELECT COUNT(*) FROM "{t}"')) for t in Base.metadata.tables}
        assert before == after
        assert after["users"] == 6 and after["conversations"] == 6 and after["messages"] == 40
        assert db.execute(text("PRAGMA foreign_key_check")).all() == []
    with Session(db_engine) as db:
        assert db.get(User, snapshot[0]).display_name == "Edited locally"
        assert db.scalar(select(Message).where(Message.id == snapshot[1])).body == "Preserve this edit"
        assert db.get(ConversationMember, snapshot[2:]).last_read_sequence == 0
        assert db.scalars(select(User)).first().created_at.tzinfo == timezone.utc


@pytest.mark.parametrize("case", ["orphan", "self_contact", "duplicate_pair", "reversed_pair", "bad_role", "unnamed_group", "duplicate_send", "invalid_receipt", "missing_identifier"])
def test_database_rejects_invalid_rows(db_engine, case):
    with Session(db_engine) as db, db.begin():
        seed_demo(db)
    with Session(db_engine) as db:
        user = db.scalars(select(User)).first()
        group = db.scalar(select(Conversation).where(Conversation.kind == "group"))
        pair = db.scalars(select(DirectPair)).first()
        message = db.scalars(select(Message)).first()
        absent_user = db.scalar(select(User).where(~User.id.in_(select(ConversationMember.user_id).where(ConversationMember.conversation_id == group.id))))
        now = datetime.now(timezone.utc)
        rows = {
            "orphan": Contact(owner_user_id=user.id, contact_user_id="missing"),
            "self_contact": Contact(owner_user_id=user.id, contact_user_id=user.id),
            "duplicate_pair": DirectPair(conversation_id=group.id, user_low_id=pair.user_low_id, user_high_id=pair.user_high_id),
            "reversed_pair": DirectPair(conversation_id=group.id, user_low_id=pair.user_high_id, user_high_id=pair.user_low_id),
            "bad_role": ConversationMember(conversation_id=group.id, user_id=absent_user.id, role="owner"),
            "unnamed_group": Conversation(kind="group", created_by=user.id),
            "duplicate_send": Message(conversation_id=message.conversation_id, sender_id=message.sender_id, client_message_id=message.client_message_id, body="Duplicate", kind="text"),
            "invalid_receipt": MessageReceipt(message_id=message.id, recipient_user_id=message.sender_id, delivered_at=now, read_at=now - timedelta(seconds=1)),
            "missing_identifier": User(display_name="No identifier"),
        }
        with pytest.raises(IntegrityError):
            db.add(rows[case])
            db.commit()


def test_health_and_cors(db_engine):
    with db_engine.begin() as db:
        db.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
        db.execute(text("INSERT INTO alembic_version VALUES ('0001')"))

    def override_db():
        with Session(db_engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        async def verify():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
                response = await client.get("/health", headers={"Origin": "http://localhost:3000"})
                assert response.json() == {"status": "ok", "database": "ok"}
                assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
                assert response.headers["access-control-allow-credentials"] == "true"
                preflight = await client.options("/health", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"})
                assert preflight.status_code == 200
                rejected = await client.options("/health", headers={"Origin": "http://untrusted.example", "Access-Control-Request-Method": "GET"})
                assert rejected.status_code == 400
                assert "access-control-allow-origin" not in rejected.headers
        asyncio.run(verify())
    finally:
        app.dependency_overrides.clear()


def test_health_rejects_uninitialized_database(db_engine):
    def override_db():
        with Session(db_engine) as db:
            yield db
    app.dependency_overrides[get_db] = override_db
    try:
        async def verify():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
                assert (await client.get("/health")).status_code == 503
        asyncio.run(verify())
    finally:
        app.dependency_overrides.clear()
