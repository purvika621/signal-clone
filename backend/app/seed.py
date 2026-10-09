"""Stable, additive fixtures. Existing rows and activity are never overwritten."""
from datetime import datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from app.models import Contact, Conversation, ConversationMember, DirectPair, Message, MessageReceipt, User, UserSettings


def fixture_id(key: str) -> str:
    return str(uuid5(NAMESPACE_URL, "signal-clone-demo/" + key))


def ensure(db: Session, model, values: dict, identity_columns: list[str]) -> bool:
    result = db.execute(insert(model).values(**values).on_conflict_do_nothing(index_elements=identity_columns))
    return result.rowcount == 1


def seed_demo(db: Session) -> None:
    start = datetime(2026, 10, 8, 9, 0, tzinfo=timezone.utc)
    names = ["Alex Morgan", "Maya Johnson", "Kai Guo", "Paige Hall", "Julian Rocha", "Sam Patel"]
    users = [fixture_id(f"user/{i}") for i in range(len(names))]
    for i, name in enumerate(names):
        ensure(db, User, {"id": users[i], "username": name.split()[0].lower(), "display_name": name, "created_at": start}, ["id"])
        ensure(db, UserSettings, {"user_id": users[i], "privacy_json": {}, "notifications_json": {}, "appearance_json": {}, "updated_at": start}, ["user_id"])
    for i in range(len(names)):
        for j in range(len(names)):
            if i != j:
                ensure(db, Contact, {"owner_user_id": users[i], "contact_user_id": users[j], "created_at": start}, ["owner_user_id", "contact_user_id"])

    definitions = [("direct", None, [0, 1]), ("direct", None, [0, 2]), ("direct", None, [0, 3]), ("direct", None, [1, 4]), ("group", "Roommates", [0, 1, 2]), ("group", "Weekend plans", [0, 3, 4, 5])]
    phrases = ["Are we still meeting tomorrow?", "Yes, see you at seven.", "I found a great place nearby.", "That sounds good to me!", "I'll send the address later.", "Thanks!\nLooking forward to it.", "Let's confirm before we leave."]
    for c, (kind, title, members) in enumerate(definitions):
        cid = fixture_id(f"conversation/{c}")
        count = 7 if c < 4 else 6  # 40 messages overall
        ensure(db, Conversation, {"id": cid, "kind": kind, "title": title, "created_by": users[members[0]], "created_at": start, "last_activity_at": start + timedelta(hours=c, minutes=count)}, ["id"])
        if kind == "direct":
            low, high = sorted(users[m] for m in members)
            ensure(db, DirectPair, {"conversation_id": cid, "user_low_id": low, "user_high_id": high}, ["conversation_id"])
        new_members = []
        for position, member in enumerate(members):
            added = ensure(db, ConversationMember, {"conversation_id": cid, "user_id": users[member], "role": "admin" if kind == "group" and position < 2 else "member", "joined_at": start, "last_read_sequence": 0}, ["conversation_id", "user_id"])
            if added:
                new_members.append(member)
        for m in range(count):
            sender = users[members[m % len(members)]]
            mid = fixture_id(f"message/{c}/{m}")
            when = start + timedelta(hours=c, minutes=m + 1)
            ensure(db, Message, {"id": mid, "conversation_id": cid, "sender_id": sender, "client_message_id": mid, "kind": "text", "body": phrases[m], "created_at": when}, ["id"])
            for member in members:
                recipient = users[member]
                if recipient == sender:
                    continue
                delivered = when + timedelta(seconds=1) if m < count - 1 else None
                read = when + timedelta(seconds=5) if m < count - 2 else None
                ensure(db, MessageReceipt, {"message_id": mid, "recipient_user_id": recipient, "delivered_at": delivered, "read_at": read}, ["message_id", "recipient_user_id"])
        # Initialize cursors only for new memberships; preserve every existing cursor.
        for member in new_members:
            uid = users[member]
            read_sequence = db.scalar(select(Message.sequence).join(MessageReceipt, MessageReceipt.message_id == Message.id).where(Message.conversation_id == cid, MessageReceipt.recipient_user_id == uid, MessageReceipt.read_at.is_not(None)).order_by(Message.sequence.desc()).limit(1))
            if read_sequence is not None:
                db.execute(update(ConversationMember).where(ConversationMember.conversation_id == cid, ConversationMember.user_id == uid, ConversationMember.last_read_sequence == 0).values(last_read_sequence=read_sequence))
