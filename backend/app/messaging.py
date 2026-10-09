"""Read-only messaging queries plus contacts and idempotent direct creation."""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.auth import CurrentUser, Db, mutation_origin
from app.models import Contact, Conversation, ConversationMember, DirectPair, Message, MessageReceipt, User
from app.schemas import ContactInput, ContactOut, ConversationOut, DirectInput, HistoryOut, MessageOut, UserOut
from app.realtime import manager

router = APIRouter(prefix="/api/v1", dependencies=[Depends(mutation_origin)])


def public_user(user):
    return UserOut.model_validate(user).model_copy(update={"online": manager.online(user.id)})


def presence_label(user):
    if manager.online(user.id):
        return "Online"
    return f"Last seen {user.last_seen_at.isoformat()}" if user.last_seen_at else "Offline"


def member_conversation(db, conversation_id: str, user_id: str):
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(404, "Conversation not found")
    membership = db.get(ConversationMember, (conversation_id, user_id))
    if membership is None or membership.left_at is not None:
        raise HTTPException(403, "You do not have access to this conversation")
    return conversation, membership


def message_out(message: Message, user_id: str) -> MessageOut:
    receipt = None
    if message.kind == "text" and message.sender_id == user_id:
        recipients = [r for r in message.receipts if r.recipient_user_id != user_id]
        receipt = "sent"
        if recipients and all(r.read_at is not None for r in recipients):
            receipt = "read"
        elif recipients and all(r.delivered_at is not None for r in recipients):
            receipt = "delivered"
    return MessageOut(id=message.id, sequence=message.sequence, client_message_id=message.client_message_id, kind=message.kind,
        body=message.body, created_at=message.created_at,
        sender=public_user(message.sender) if message.sender else None, receipt=receipt)


def conversation_out(db, conversation: Conversation, member: ConversationMember, user_id: str):
    other = None
    title = conversation.title or "Conversation"
    avatar = conversation.avatar_url
    if conversation.kind == "direct":
        other = db.scalar(select(User).join(ConversationMember).where(
            ConversationMember.conversation_id == conversation.id, User.id != user_id))
        if other is not None:
            contact = db.get(Contact, (user_id, other.id))
            title = (contact.alias if contact else None) or other.display_name
            avatar = other.avatar_url
    latest = db.scalar(select(Message).where(Message.conversation_id == conversation.id)
        .options(selectinload(Message.receipts), selectinload(Message.sender))
        .order_by(Message.sequence.desc()).limit(1))
    unread = db.scalar(select(func.count()).select_from(Message).join(MessageReceipt, MessageReceipt.message_id == Message.id).where(
        Message.conversation_id == conversation.id, Message.kind == "text",
        Message.sender_id != user_id, Message.sequence > member.last_read_sequence,
        MessageReceipt.recipient_user_id == user_id))
    return ConversationOut(id=conversation.id, kind=conversation.kind, title=title, avatar_url=avatar,
        other_user=public_user(other) if other else None, last_activity_at=conversation.last_activity_at,
        unread_count=unread or 0, latest_message=message_out(latest, user_id) if latest else None)


def user_search(statement, query: str):
    # Autoescape makes %, _ and backslashes literal search terms.
    term = query.strip()
    return statement.where(or_(User.display_name.icontains(term, autoescape=True),
        User.username.icontains(term, autoescape=True), User.phone_e164.icontains(term, autoescape=True)))


@router.get("/users", response_model=list[UserOut])
def find_users(user: CurrentUser, db: Db, query: Annotated[str, Query(min_length=2, max_length=100)]):
    return [public_user(u) for u in db.scalars(user_search(select(User).where(User.id != user.id), query)
                          .order_by(User.display_name, User.id).limit(30))]


@router.get("/contacts", response_model=list[ContactOut])
def contacts(user: CurrentUser, db: Db, query: Annotated[str, Query(max_length=100)] = ""):
    statement = select(Contact).join(User, Contact.contact_user_id == User.id).where(Contact.owner_user_id == user.id)
    if query.strip():
        term = query.strip()
        statement = statement.where(or_(Contact.alias.icontains(term, autoescape=True),
            User.display_name.icontains(term, autoescape=True), User.username.icontains(term, autoescape=True),
            User.phone_e164.icontains(term, autoescape=True)))
    return [ContactOut(user=public_user(c.contact), alias=c.alias, presence=presence_label(c.contact))
            for c in db.scalars(statement.options(selectinload(Contact.contact)).order_by(User.display_name, User.id))]


@router.post("/contacts", response_model=ContactOut, status_code=201)
def add_contact(body: ContactInput, user: CurrentUser, db: Db):
    if body.contact_user_id == user.id:
        raise HTTPException(422, "You cannot add yourself as a contact")
    other = db.get(User, body.contact_user_id)
    if other is None:
        raise HTTPException(404, "Registered user not found")
    contact = Contact(owner_user_id=user.id, contact_user_id=other.id, alias=body.alias)
    db.add(contact)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "This user is already in your contacts") from exc
    return ContactOut(user=public_user(other), alias=contact.alias, presence=presence_label(other))


@router.get("/conversations", response_model=list[ConversationOut])
def inbox(user: CurrentUser, db: Db, query: Annotated[str, Query(max_length=100)] = "",
          filter: Literal["all", "unread"] = "all"):
    rows = db.execute(select(Conversation, ConversationMember).join(ConversationMember).where(
        ConversationMember.user_id == user.id, ConversationMember.left_at.is_(None))
        .order_by(Conversation.last_activity_at.desc(), Conversation.id)).all()
    items = [conversation_out(db, conversation, member, user.id) for conversation, member in rows]
    term = query.strip().lower()
    return [c for c in items if (filter == "all" or c.unread_count > 0) and
            (not term or term in c.title.lower() or (c.latest_message and term in c.latest_message.body.lower()))]


@router.post("/conversations/direct", response_model=ConversationOut)
async def direct(body: DirectInput, user: CurrentUser, db: Db):
    if db.get(Contact, (user.id, body.contact_user_id)) is None:
        raise HTTPException(422, "Add this user to your contacts first")
    low, high = sorted((user.id, body.contact_user_id))
    pair_query = select(DirectPair).where(DirectPair.user_low_id == low, DirectPair.user_high_id == high)
    pair = db.scalar(pair_query)
    if pair is None:
        conversation = Conversation(kind="direct", created_by=user.id)
        db.add(conversation)
        db.flush()
        db.add(DirectPair(conversation_id=conversation.id, user_low_id=low, user_high_id=high))
        db.add_all([ConversationMember(conversation_id=conversation.id, user_id=uid, role="member") for uid in (low, high)])
        try:
            db.commit()
        except IntegrityError:
            # The unique ordered pair arbitrates concurrent requests; rolling back
            # also removes the losing conversation and both memberships.
            db.rollback()
            pair = db.scalar(pair_query)
            if pair is None:
                raise HTTPException(409, "Conversation creation conflicted. Please retry")
        else:
            pair = db.scalar(pair_query)
    conversation, member = member_conversation(db, pair.conversation_id, user.id)
    from app.message_service import commit_events
    commit_events(db, conversation.id, "conversation.updated")
    return conversation_out(db, conversation, member, user.id)


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
def details(conversation_id: str, user: CurrentUser, db: Db):
    conversation, member = member_conversation(db, conversation_id, user.id)
    return conversation_out(db, conversation, member, user.id)


@router.get("/conversations/{conversation_id}/messages", response_model=HistoryOut)
def history(conversation_id: str, user: CurrentUser, db: Db,
            before_sequence: Annotated[int | None, Query(gt=0)] = None,
            limit: Annotated[int, Query(ge=1, le=100)] = 100):
    member_conversation(db, conversation_id, user.id)
    statement = select(Message).where(Message.conversation_id == conversation_id)
    if before_sequence is not None:
        statement = statement.where(Message.sequence < before_sequence)
    rows = list(db.scalars(statement.options(selectinload(Message.receipts), selectinload(Message.sender))
                           .order_by(Message.sequence.desc()).limit(limit + 1)))
    has_more = len(rows) > limit
    messages = list(reversed(rows[:limit]))
    return HistoryOut(items=[message_out(m, user.id) for m in messages],
                      next_cursor=messages[0].sequence if has_more else None)
