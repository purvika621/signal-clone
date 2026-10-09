"""SQLite transactions and addressed events shared by HTTP and WebSocket ACKs."""
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.messaging import conversation_out, member_conversation, message_out
from app.models import Contact, ConversationMember, Message, MessageReceipt, User, UserEvent, now_utc
from app.realtime import manager


def members(db, conversation_id):
    return list(db.scalars(select(ConversationMember.user_id).where(
        ConversationMember.conversation_id == conversation_id, ConversationMember.left_at.is_(None))))


def commit_events(db, conversation_id, event_type, changed_ids=(), removed=(), added=()):
    """Create recipient-specific snapshots in the same transaction, commit, enqueue."""
    db.flush()
    db.expire_all()
    conversation = member_conversation(db, conversation_id, members(db, conversation_id)[0])[0]
    changed = list(db.scalars(select(Message).where(Message.id.in_(changed_ids))
        .options(selectinload(Message.receipts), selectinload(Message.sender)))) if changed_ids else []
    events = []
    for user_id in members(db, conversation_id):
        member = db.get(ConversationMember, (conversation_id, user_id))
        payload = {"conversation_id": conversation_id,
                   "conversation": conversation_out(db, conversation, member, user_id).model_dump(mode="json"),
                   "messages": [message_out(m, user_id).model_dump(mode="json") for m in changed]}
        event = UserEvent(user_id=user_id, type=event_type, payload_json=payload)
        db.add(event)
        events.append(event)
    for user_id in removed:
        event = UserEvent(user_id=user_id, type="conversation.access_revoked",
                          payload_json={"conversation_id": conversation_id})
        db.add(event)
        events.append(event)
    db.flush()
    for user_id in {e.user_id for e in events}:
        oldest = db.scalar(select(UserEvent.sequence).where(UserEvent.user_id == user_id)
                           .order_by(UserEvent.sequence.desc()).offset(999).limit(1))
        if oldest is not None:
            db.execute(delete(UserEvent).where(UserEvent.user_id == user_id, UserEvent.sequence < oldest))
    db.commit()
    manager.membership_changed(conversation_id, removed, added)
    for event in events:
        manager.emit([event.user_id], event_envelope(event))


def event_envelope(event):
    return {"event_id": event.sequence, "type": event.type,
            "conversation_id": event.payload_json.get("conversation_id"),
            "occurred_at": event.created_at.isoformat(), "payload": event.payload_json}


def send_message(db, user_id, conversation_id, body):
    conversation, _ = member_conversation(db, conversation_id, user_id)
    client_id = str(body.client_message_id)
    lookup = select(Message).where(Message.sender_id == user_id, Message.client_message_id == client_id)
    existing = db.scalar(lookup)
    if existing:
        if existing.conversation_id != conversation_id or existing.body != body.body:
            raise HTTPException(409, "This client message ID was already used for different content")
        return message_out(existing, user_id)
    message = Message(conversation_id=conversation_id, sender_id=user_id,
                      client_message_id=client_id, kind="text", body=body.body)
    db.add(message)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(lookup)
        if existing is None or existing.conversation_id != conversation_id or existing.body != body.body:
            raise HTTPException(409, "Message creation conflicted")
        return message_out(existing, user_id)
    db.add_all([MessageReceipt(message_id=message.id, recipient_user_id=uid)
                for uid in members(db, conversation_id) if uid != user_id])
    conversation.last_activity_at = message.created_at
    commit_events(db, conversation_id, "message.created", [message.id])
    for connection in list(manager.connections):
        if connection.user_id == user_id:
            manager.set_typing(connection, conversation_id, [], False)
    return message_out(message, user_id)


def acknowledge_delivery(db, user_id, conversation_id, message_ids):
    member_conversation(db, conversation_id, user_id)
    ids = {str(mid) for mid in message_ids}
    rows = db.execute(select(Message, MessageReceipt).join(MessageReceipt, MessageReceipt.message_id == Message.id)
        .where(Message.id.in_(ids), MessageReceipt.recipient_user_id == user_id)).all()
    if len(rows) != len(ids) or any(m.conversation_id != conversation_id or m.sender_id == user_id for m, _ in rows):
        raise HTTPException(403, "You can acknowledge only messages addressed to you in this conversation")
    changed = []
    for message, receipt in rows:
        if receipt.delivered_at is None:
            receipt.delivered_at = now_utc()
            changed.append(message.id)
    if changed:
        commit_events(db, conversation_id, "message.receipt_updated", changed)


def acknowledge_read(db, user_id, conversation_id, through_sequence):
    conversation, member = member_conversation(db, conversation_id, user_id)
    target = db.get(Message, through_sequence)
    if target is None or target.conversation_id != conversation_id:
        raise HTTPException(422, "Read cursor must identify a message in this conversation")
    rows = db.execute(select(Message, MessageReceipt).join(MessageReceipt, MessageReceipt.message_id == Message.id).where(
        Message.conversation_id == conversation_id, Message.sequence <= through_sequence,
        MessageReceipt.recipient_user_id == user_id, Message.sender_id != user_id)).all()
    changed = []
    for message, receipt in rows:
        if receipt.read_at is None:
            now = now_utc()
            receipt.delivered_at = receipt.delivered_at or now
            receipt.read_at = max(now, receipt.delivered_at)
            changed.append(message.id)
    advanced = member.last_read_sequence < through_sequence
    member.last_read_sequence = max(member.last_read_sequence, through_sequence)
    if changed or advanced:
        commit_events(db, conversation_id, "message.receipt_updated", changed)
    return conversation_out(db, conversation, member, user_id)


def presence_audience(db, user_id):
    shared = select(ConversationMember.conversation_id).where(ConversationMember.user_id == user_id, ConversationMember.left_at.is_(None))
    return set(db.scalars(select(Contact.owner_user_id).where(Contact.contact_user_id == user_id))) | set(
        db.scalars(select(ConversationMember.user_id).where(ConversationMember.conversation_id.in_(shared), ConversationMember.left_at.is_(None))))


def presence_changed(db, user_id):
    user = db.get(User, user_id)
    online = manager.online(user_id)
    if not online:
        user.last_seen_at = now_utc()
        db.commit()
    manager.emit(presence_audience(db, user_id), {"type": "presence.updated", "occurred_at": now_utc().isoformat(),
        "payload": {"user_id": user_id, "online": online, "last_seen_at": user.last_seen_at.isoformat() if user.last_seen_at else None}})
