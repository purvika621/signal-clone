import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.exc import SQLAlchemyError

from app.auth import COOKIE_NAME, CurrentUser, Db, mutation_origin, validated_session
from app.config import settings
from app.message_service import acknowledge_delivery, acknowledge_read, commit_events, event_envelope, members, presence_changed, send_message
from app.messaging import member_conversation, message_out
from app.models import ConversationMember, Message, MessageReceipt, MessageReaction, UserEvent
from app.realtime import Connection, manager
from app.schemas import ConversationOut, DeliveryInput, MessageOut, ReadInput, SendInput, TypingInput, ReactionInput

router = APIRouter(prefix="/api/v1")


@router.post("/conversations/{conversation_id}/messages", response_model=MessageOut, dependencies=[])
async def send(conversation_id: str, body: SendInput, user: CurrentUser, db: Db):
    return send_message(db, user.id, conversation_id, body)


@router.post("/conversations/{conversation_id}/messages/{message_id}/reactions", response_model=MessageOut)
async def reaction(conversation_id: str, message_id: str, body: ReactionInput, user: CurrentUser, db: Db):
    member_conversation(db, conversation_id, user.id)
    message = db.scalar(select(Message).where(Message.id == message_id, Message.conversation_id == conversation_id))
    if message is None:
        raise HTTPException(404, "Message not found in this conversation")
    if message.kind != "text":
        raise HTTPException(422, "Only text messages support reactions")
    if body.active:
        result = db.execute(insert(MessageReaction).values(message_id=message_id, user_id=user.id, emoji=body.emoji).on_conflict_do_nothing())
    else:
        result = db.execute(delete(MessageReaction).where(MessageReaction.message_id == message_id, MessageReaction.user_id == user.id, MessageReaction.emoji == body.emoji))
    if result.rowcount:
        db.execute(update(Message).where(Message.id == message_id).values(reaction_version=Message.reaction_version + 1))
        commit_events(db, conversation_id, "message.reactions_updated", [message_id])
    else:
        db.commit()
        db.expire_all()
    return message_out(message, user.id)


@router.post("/conversations/{conversation_id}/delivered")
async def delivered(conversation_id: str, body: DeliveryInput, user: CurrentUser, db: Db):
    acknowledge_delivery(db, user.id, conversation_id, body.message_ids)
    return {"ok": True}


@router.post("/conversations/{conversation_id}/read", response_model=ConversationOut)
async def read(conversation_id: str, body: ReadInput, user: CurrentUser, db: Db):
    return acknowledge_read(db, user.id, conversation_id, body.through_sequence)


@router.get("/messages/pending-delivery")
def pending_delivery(user: CurrentUser, db: Db):
    rows = db.execute(select(Message.conversation_id, Message.id).join(MessageReceipt, MessageReceipt.message_id == Message.id)
        .join(ConversationMember, ConversationMember.conversation_id == Message.conversation_id).where(
        ConversationMember.user_id == user.id, ConversationMember.left_at.is_(None),
        MessageReceipt.recipient_user_id == user.id, MessageReceipt.delivered_at.is_(None), Message.sender_id != user.id)
        .order_by(Message.sequence).limit(100)).all()
    groups = {}
    for cid, mid in rows:
        groups.setdefault(cid, []).append(mid)
    return [{"conversation_id": cid, "message_ids": ids} for cid, ids in groups.items()]


@router.websocket("/ws")
async def socket(websocket: WebSocket, db: Db, cursor: Annotated[int, Query(ge=0)] = 0):
    if websocket.headers.get("origin") != (settings.websocket_origin or settings.frontend_origin):
        await websocket.close(code=1008)
        return
    try:
        session = validated_session(db, websocket.cookies.get(COOKIE_NAME))
    except HTTPException:
        await websocket.close(code=1008)
        return
    uid, sid, name = session.user_id, session.id, session.user.display_name
    db.rollback()
    await websocket.accept()
    connection = Connection(websocket, uid, sid, name)
    was_online = manager.online(uid)
    manager.register(connection)
    try:
        last = db.scalar(select(func.max(UserEvent.sequence)).where(UserEvent.user_id == uid)) or 0
        manager.enqueue(connection, {"type": "session.ready", "payload": {"user_id": uid, "cursor": last}})
        replay = list(db.scalars(select(UserEvent).where(UserEvent.user_id == uid, UserEvent.sequence > cursor).order_by(UserEvent.sequence).limit(201))) if cursor else []
        if cursor and len(replay) <= 200 and cursor <= last:
            for event in replay:
                cid = event.payload_json.get("conversation_id")
                member = db.get(ConversationMember, (cid, uid)) if cid else None
                if (event.type == "conversation.access_revoked" and member and member.left_at is not None) or (event.type != "conversation.access_revoked" and member and member.left_at is None):
                    manager.enqueue(connection, event_envelope(event))
        manager.enqueue(connection, {"type": "sync.required", "payload": {"cursor": last}})
        if not was_online:
            presence_changed(db, uid)
        db.rollback()
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=20)
            except asyncio.TimeoutError:
                raw = '{"type":"ping"}'
            db.expire_all()
            try:
                valid = validated_session(db, websocket.cookies.get(COOKIE_NAME))
                if valid.id != sid:
                    raise HTTPException(401, "Session changed")
            except HTTPException:
                await manager.close(connection)
                break
            db.rollback()
            try:
                if len(raw) > 16000:
                    raise HTTPException(422, "WebSocket command is too large")
                command = json.loads(raw)
                if not isinstance(command, dict):
                    raise HTTPException(422, "Expected a command object")
                kind = command.get("type")
                if kind == "ping":
                    manager.enqueue(connection, {"type": "pong", "payload": {}})
                    continue
                cid = command.get("conversation_id")
                if not isinstance(cid, str):
                    raise HTTPException(422, "conversation_id is required")
                if kind == "message.delivered":
                    body = DeliveryInput.model_validate({k: v for k, v in command.items() if k not in {"type", "conversation_id"}})
                    acknowledge_delivery(db, uid, cid, body.message_ids)
                elif kind == "conversation.read":
                    body = ReadInput.model_validate({k: v for k, v in command.items() if k not in {"type", "conversation_id"}})
                    acknowledge_read(db, uid, cid, body.through_sequence)
                elif kind in {"typing.started", "typing.stopped"}:
                    TypingInput.model_validate({k: v for k, v in command.items() if k != "type"})
                    member_conversation(db, cid, uid)
                    manager.set_typing(connection, cid, [u for u in members(db, cid) if u != uid], kind == "typing.started")
                else:
                    raise HTTPException(422, "Unknown WebSocket command")
            except (HTTPException, ValidationError, ValueError) as exc:
                manager.enqueue(connection, {"type": "error", "payload": {"code": "forbidden" if isinstance(exc, HTTPException) and exc.status_code == 403 else "invalid_command", "message": str(exc.detail) if isinstance(exc, HTTPException) else "Invalid command fields"}})
            except SQLAlchemyError:
                manager.enqueue(connection, {"type": "error", "payload": {"code": "unavailable", "message": "Database temporarily unavailable"}})
            finally:
                db.rollback()
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        manager.remove(connection)
        db.rollback()
        if not manager.online(uid):
            try:
                presence_changed(db, uid)
            except SQLAlchemyError:
                db.rollback()
