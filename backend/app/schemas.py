"""Phase 3B contracts. Input bodies reject unknown fields."""
import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

AVATARS = {f"/avatars/{name}.jpg" for name in ("alex", "maya", "kai", "paige", "family", "climbers")}


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class IdentifierInput(Input):
    identifier: str = Field(min_length=3, max_length=100)

    @field_validator("identifier")
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        if value.startswith("+"):
            if not re.fullmatch(r"\+[1-9][0-9]{7,14}", value):
                raise ValueError("Use an international phone number, such as +919876543210")
            return value
        value = value.lower()
        if not re.fullmatch(r"[a-z][a-z0-9_.-]{2,49}", value):
            raise ValueError("Username must start with a letter and contain 3–50 letters, digits, dots, underscores or hyphens")
        return value


class VerifyInput(IdentifierInput):
    otp: str = Field(pattern=r"^[0-9]{6}$")


class ProfileInput(Input):
    display_name: str = Field(min_length=1, max_length=100)
    avatar_url: str

    @field_validator("avatar_url")
    @classmethod
    def supported_avatar(cls, value: str) -> str:
        if value not in AVATARS:
            raise ValueError("Choose one of the provided profile avatars")
        return value


class ContactInput(Input):
    contact_user_id: str = Field(min_length=1, max_length=36)
    alias: str | None = Field(default=None, min_length=1, max_length=100)


class DirectInput(Input):
    contact_user_id: str = Field(min_length=1, max_length=36)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    username: str | None
    phone_e164: str | None
    display_name: str
    avatar_url: str | None
    online: bool = False
    last_seen_at: datetime | None = None


class SessionOut(BaseModel):
    user: UserOut
    needs_profile: bool


class ChallengeOut(BaseModel):
    identifier: str
    mock_code: str
    message: str


class ContactOut(BaseModel):
    user: UserOut
    alias: str | None
    presence: str = "Offline"


class ReactionOut(BaseModel):
    user_id: str
    emoji: Literal["❤️", "😂", "👍", "😮", "😢", "🎉"]


class ReactionInput(Input):
    emoji: Literal["❤️", "😂", "👍", "😮", "😢", "🎉"]
    active: bool


class MessageOut(BaseModel):
    id: str
    sequence: int
    client_message_id: str | None
    kind: Literal["text", "system"]
    body: str
    created_at: datetime
    sender: UserOut | None
    receipt: Literal["sent", "delivered", "read"] | None
    reactions: list[ReactionOut] = Field(default_factory=list)
    reaction_version: int = 0


class ConversationOut(BaseModel):
    id: str
    kind: Literal["direct", "group"]
    title: str
    avatar_url: str | None
    other_user: UserOut | None
    last_activity_at: datetime
    unread_count: int
    latest_message: MessageOut | None


class HistoryOut(BaseModel):
    items: list[MessageOut]
    next_cursor: int | None


class SendInput(Input):
    client_message_id: UUID
    body: str = Field(min_length=1, max_length=4000)


class ReadInput(Input):
    through_sequence: int = Field(gt=0)


class DeliveryInput(Input):
    message_ids: list[UUID] = Field(min_length=1, max_length=100)


class TypingInput(Input):
    conversation_id: UUID


class MembersInput(Input):
    member_ids: list[UUID] = Field(min_length=1, max_length=99)

    @field_validator("member_ids")
    @classmethod
    def unique_members(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("Select each member only once")
        return value


class GroupInput(MembersInput):
    client_group_id: UUID
    title: str = Field(min_length=1, max_length=100)


class GroupEditInput(Input):
    title: str = Field(min_length=1, max_length=100)


class RoleInput(Input):
    role: Literal["admin", "member"]


class GroupMemberOut(BaseModel):
    user: UserOut
    role: Literal["admin", "member"]
    joined_at: datetime


class GroupOut(BaseModel):
    conversation: ConversationOut
    members: list[GroupMemberOut]
    my_role: Literal["admin", "member"]
