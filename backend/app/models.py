from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database import Base, UTCDateTime


def new_id() -> str:
    return str(uuid4())


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("username IS NOT NULL OR phone_e164 IS NOT NULL", name="ck_users_identifier"),
        CheckConstraint("username IS NULL OR (length(trim(username)) > 0 AND username = lower(trim(username)))", name="ck_users_username"),
        CheckConstraint("phone_e164 IS NULL OR length(trim(phone_e164)) > 0", name="ck_users_phone"),
        CheckConstraint("length(trim(display_name)) > 0", name="ck_users_display_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    username: Mapped[str | None] = mapped_column(String(100), unique=True)
    phone_e164: Mapped[str | None] = mapped_column(String(16), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    avatar_url: Mapped[str | None] = mapped_column(Text)
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now_utc)
    memberships: Mapped[list["ConversationMember"]] = relationship(back_populates="user")
    sessions: Mapped[list["AuthSession"]] = relationship(back_populates="user")
    settings: Mapped["UserSettings | None"] = relationship(back_populates="user", uselist=False)

    @validates("username")
    def normalize_username(self, _key, value: str | None) -> str | None:
        return value.strip().lower() if value is not None else None


class AuthSession(Base):
    __tablename__ = "sessions"
    __table_args__ = (CheckConstraint("expires_at > created_at", name="ck_sessions_expiry"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now_utc)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    user: Mapped[User] = relationship(back_populates="sessions")


class Contact(Base):
    __tablename__ = "contacts"
    __table_args__ = (CheckConstraint("owner_user_id <> contact_user_id", name="ck_contacts_not_self"),)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    contact_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True, index=True)
    alias: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now_utc)
    owner: Mapped[User] = relationship(foreign_keys=[owner_user_id])
    contact: Mapped[User] = relationship(foreign_keys=[contact_user_id])


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint("kind IN ('direct', 'group')", name="ck_conversations_kind"),
        CheckConstraint("kind <> 'group' OR (title IS NOT NULL AND length(trim(title)) > 0)", name="ck_conversations_group_title"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(10))
    title: Mapped[str | None] = mapped_column(String(100))
    avatar_url: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now_utc)
    last_activity_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now_utc, index=True)
    creator: Mapped[User] = relationship()
    members: Mapped[list["ConversationMember"]] = relationship(back_populates="conversation")
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", order_by="Message.sequence")
    direct_pair: Mapped["DirectPair | None"] = relationship(back_populates="conversation", uselist=False)


class GroupCreation(Base):
    """Immutable creation intent; retries remain safe even after group edits."""
    __tablename__ = "group_creations"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    client_group_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), unique=True)
    fingerprint: Mapped[str] = mapped_column(String(64))


class DirectPair(Base):
    __tablename__ = "direct_pairs"
    __table_args__ = (
        UniqueConstraint("user_low_id", "user_high_id", name="uq_direct_pairs_users"),
        CheckConstraint("user_low_id < user_high_id", name="ck_direct_pairs_order"),
    )
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), primary_key=True)
    user_low_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    user_high_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    conversation: Mapped[Conversation] = relationship(back_populates="direct_pair")
    user_low: Mapped[User] = relationship(foreign_keys=[user_low_id])
    user_high: Mapped[User] = relationship(foreign_keys=[user_high_id])


class ConversationMember(Base):
    __tablename__ = "conversation_members"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'member')", name="ck_members_role"),
        CheckConstraint("last_read_sequence >= 0", name="ck_members_read_cursor"),
        CheckConstraint("left_at IS NULL OR left_at >= joined_at", name="ck_members_dates"),
        Index("ix_members_user_active", "user_id", "left_at"),
    )
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(10), default="member")
    joined_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now_utc)
    left_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_read_sequence: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    conversation: Mapped[Conversation] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("sender_id", "client_message_id", name="uq_messages_client_send"),
        CheckConstraint("kind IN ('text', 'system')", name="ck_messages_kind"),
        CheckConstraint("kind <> 'text' OR (sender_id IS NOT NULL AND client_message_id IS NOT NULL AND length(trim(body)) > 0)", name="ck_messages_text"),
        Index("ix_messages_conversation_sequence", "conversation_id", "sequence"),
        {"sqlite_autoincrement": True},
    )
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(36), unique=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"))
    sender_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    client_message_id: Mapped[str | None] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(10), default="text")
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now_utc)
    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    sender: Mapped[User | None] = relationship()
    receipts: Mapped[list["MessageReceipt"]] = relationship(back_populates="message")


class MessageReceipt(Base):
    __tablename__ = "message_receipts"
    __table_args__ = (
        CheckConstraint("read_at IS NULL OR (delivered_at IS NOT NULL AND read_at >= delivered_at)", name="ck_receipts_read_after_delivery"),
        Index("ix_receipts_recipient_message", "recipient_user_id", "message_id"),
    )
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), primary_key=True)
    recipient_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    delivered_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    read_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    message: Mapped[Message] = relationship(back_populates="receipts")
    recipient: Mapped[User] = relationship()


class UserSettings(Base):
    __tablename__ = "user_settings"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    privacy_json: Mapped[dict] = mapped_column(JSON, default=dict)
    notifications_json: Mapped[dict] = mapped_column(JSON, default=dict)
    appearance_json: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now_utc, onupdate=now_utc)
    user: Mapped[User] = relationship(back_populates="settings")


class UserEvent(Base):
    __tablename__ = "user_events"
    __table_args__ = (Index("ix_events_user_sequence", "user_id", "sequence"), {"sqlite_autoincrement": True})
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    type: Mapped[str] = mapped_column(String(100))
    payload_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now_utc)
    user: Mapped[User] = relationship()

