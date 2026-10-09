"""Group commands are short atomic transactions, serialized by one worker."""
import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.auth import CurrentUser, Db, mutation_origin
from app.messaging import conversation_out, member_conversation, public_user
from app.message_service import commit_events
from app.models import Contact, Conversation, ConversationMember, GroupCreation, Message, now_utc
from app.schemas import GroupEditInput, GroupInput, GroupMemberOut, GroupOut, MembersInput, RoleInput

router = APIRouter(prefix="/api/v1/groups", dependencies=[Depends(mutation_origin)])


def group_member(db, cid, uid, admin=False):
    conversation, member = member_conversation(db, cid, uid)
    if conversation.kind != "group":
        raise HTTPException(422, "This conversation is not a group")
    if admin and member.role != "admin":
        raise HTTPException(403, "Only group admins can perform this action")
    return conversation, member


def details(db, cid, uid):
    conversation, member = group_member(db, cid, uid)
    roster = list(db.scalars(select(ConversationMember).where(
        ConversationMember.conversation_id == cid, ConversationMember.left_at.is_(None))))
    roster.sort(key=lambda m: (m.role != "admin", m.user.display_name.casefold(), m.user_id))
    return GroupOut(conversation=conversation_out(db, conversation, member, uid), my_role=member.role,
        members=[GroupMemberOut(user=public_user(m.user), role=m.role, joined_at=m.joined_at) for m in roster])


def validate_contacts(db, uid, ids):
    if uid in ids:
        raise HTTPException(422, "You are already included as the creator or current member")
    available = set(db.scalars(select(Contact.contact_user_id).where(Contact.owner_user_id == uid, Contact.contact_user_id.in_(ids))))
    if set(ids) != available:
        raise HTTPException(422, "Choose members from your contacts")


def protect_admin(db, cid, member):
    count = db.scalar(select(func.count()).select_from(ConversationMember).where(
        ConversationMember.conversation_id == cid, ConversationMember.left_at.is_(None), ConversationMember.role == "admin"))
    if member.role == "admin" and count <= 1:
        raise HTTPException(409, "This is the last admin. Make another member an admin first")


def record_change(db, conversation, text, removed=(), added=()):
    message = Message(conversation_id=conversation.id, kind="system", body=text)
    db.add(message)
    db.flush()
    conversation.last_activity_at = message.created_at
    commit_events(db, conversation.id, "group.members_updated", [message.id], removed=removed, added=added)


@router.post("", response_model=GroupOut)
async def create_group(body: GroupInput, user: CurrentUser, db: Db):
    ids = sorted(str(uid) for uid in body.member_ids)
    fingerprint = hashlib.sha256(json.dumps([body.title, ids], ensure_ascii=False).encode()).hexdigest()
    key = (user.id, str(body.client_group_id))
    existing = db.get(GroupCreation, key)
    if existing:
        if existing.fingerprint != fingerprint:
            raise HTTPException(409, "This creation ID was already used for different group details")
        return details(db, existing.conversation_id, user.id)
    validate_contacts(db, user.id, ids)
    conversation = Conversation(kind="group", title=body.title, created_by=user.id)
    db.add(conversation)
    db.flush()
    db.add_all([ConversationMember(conversation_id=conversation.id, user_id=uid,
        role="admin" if uid == user.id else "member") for uid in [user.id, *ids]])
    db.add(GroupCreation(user_id=user.id, client_group_id=key[1], conversation_id=conversation.id, fingerprint=fingerprint))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.get(GroupCreation, key)
        if existing is None or existing.fingerprint != fingerprint:
            raise HTTPException(409, "Group creation conflicted. Retry the same request")
        return details(db, existing.conversation_id, user.id)
    commit_events(db, conversation.id, "group.created", added=[user.id, *ids])
    return details(db, conversation.id, user.id)


@router.get("/{cid}", response_model=GroupOut)
def get_group(cid: str, user: CurrentUser, db: Db):
    return details(db, cid, user.id)


@router.get("/{cid}/members", response_model=list[GroupMemberOut])
def get_members(cid: str, user: CurrentUser, db: Db):
    return details(db, cid, user.id).members


@router.patch("/{cid}", response_model=GroupOut)
async def rename(cid: str, body: GroupEditInput, user: CurrentUser, db: Db):
    conversation, _ = group_member(db, cid, user.id, admin=True)
    if conversation.title != body.title:
        conversation.title = body.title
        record_change(db, conversation, f"{user.display_name} changed the group name to {body.title}")
    return details(db, cid, user.id)


@router.post("/{cid}/members", response_model=GroupOut)
async def add_members(cid: str, body: MembersInput, user: CurrentUser, db: Db):
    conversation, _ = group_member(db, cid, user.id, admin=True)
    ids = [str(uid) for uid in body.member_ids]
    validate_contacts(db, user.id, ids)
    active = list(db.scalars(select(ConversationMember).where(ConversationMember.conversation_id == cid, ConversationMember.left_at.is_(None))))
    if len(active) + len(ids) > 100:
        raise HTTPException(422, "Groups support up to 100 members")
    if any(m.user_id in ids for m in active):
        raise HTTPException(409, "A selected contact is already a member")
    sequence = db.scalar(select(func.max(Message.sequence)).where(Message.conversation_id == cid)) or 0
    for uid in ids:
        member = db.get(ConversationMember, (cid, uid))
        if member:
            member.left_at = None
            member.joined_at = now_utc()
            member.role = "member"
            member.last_read_sequence = sequence
        else:
            db.add(ConversationMember(conversation_id=cid, user_id=uid, role="member", last_read_sequence=sequence))
    record_change(db, conversation, f"{user.display_name} added {len(ids)} member{'s' if len(ids) != 1 else ''}", added=ids)
    return details(db, cid, user.id)


@router.patch("/{cid}/members/{uid}", response_model=GroupOut)
async def change_role(cid: str, uid: str, body: RoleInput, user: CurrentUser, db: Db):
    conversation, _ = group_member(db, cid, user.id, admin=True)
    _, target = group_member(db, cid, uid)
    if target.role != body.role:
        if body.role == "member":
            protect_admin(db, cid, target)
        target.role = body.role
        record_change(db, conversation, f"{target.user.display_name} is now {'an admin' if body.role == 'admin' else 'a member'}")
    return details(db, cid, user.id)


@router.delete("/{cid}/members/{uid}", response_model=GroupOut)
async def remove_member(cid: str, uid: str, user: CurrentUser, db: Db):
    conversation, _ = group_member(db, cid, user.id, admin=True)
    if uid == user.id:
        raise HTTPException(422, "Use Leave group to remove yourself")
    _, target = group_member(db, cid, uid)
    protect_admin(db, cid, target)
    target.left_at = now_utc()
    record_change(db, conversation, f"{user.display_name} removed {target.user.display_name}", removed=[uid])
    return details(db, cid, user.id)


@router.post("/{cid}/leave")
async def leave(cid: str, user: CurrentUser, db: Db):
    conversation, member = group_member(db, cid, user.id)
    protect_admin(db, cid, member)
    member.left_at = now_utc()
    record_change(db, conversation, f"{user.display_name} left the group", removed=[user.id])
    return {"ok": True}
