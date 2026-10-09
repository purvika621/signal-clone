"""Single-worker WebSocket connections. Each writer owns its socket output."""
import asyncio
import time
from dataclasses import dataclass, field
from datetime import timedelta
from uuid import uuid4

from fastapi import WebSocket
from app.models import now_utc


@dataclass(eq=False)
class Connection:
    socket: WebSocket
    user_id: str
    session_id: str
    name: str
    id: str = field(default_factory=lambda: str(uuid4()))
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=256))
    writer: asyncio.Task | None = None
    denied_conversations: set[str] = field(default_factory=set)


class ConnectionManager:
    def __init__(self):
        self.connections: set[Connection] = set()
        self.typing: dict[tuple[Connection, str], dict] = {}

    def online(self, user_id):
        return any(c.user_id == user_id for c in list(self.connections))

    def enqueue(self, connection, event):
        if event.get("conversation_id") in connection.denied_conversations and event["type"] != "conversation.access_revoked":
            return
        try:
            connection.queue.put_nowait(event)
        except asyncio.QueueFull:
            # A slow client reconnects and recovers from SQLite, rather than
            # letting an unbounded queue retain message history in memory.
            asyncio.create_task(self.close(connection, 1013))

    def emit(self, users, event):
        users = set(users)
        for connection in list(self.connections):
            if connection.user_id in users:
                self.enqueue(connection, event)

    async def write(self, connection):
        try:
            while True:
                event = await connection.queue.get()
                if event.get("conversation_id") in connection.denied_conversations and event["type"] != "conversation.access_revoked":
                    continue
                await asyncio.wait_for(connection.socket.send_json(event), timeout=10)
        except (Exception, asyncio.CancelledError):
            try:
                await connection.socket.close(code=1013)
            except Exception:
                pass

    def register(self, connection):
        self.connections.add(connection)
        connection.writer = asyncio.create_task(self.write(connection))

    async def close(self, connection, code=1008):
        if connection.writer:
            connection.writer.cancel()
        try:
            await connection.socket.close(code=code)
        except Exception:
            pass

    async def revoke(self, session_id):
        for connection in list(self.connections):
            if connection.session_id == session_id:
                await self.close(connection)

    def membership_changed(self, conversation_id, removed=(), added=()):
        """Cut off existing sockets and queued private frames before fan-out."""
        removed = set(removed)
        for (connection, cid), value in list(self.typing.items()):
            if cid == conversation_id:
                value["recipients"] = [uid for uid in value["recipients"] if uid not in removed]
                if connection.user_id in removed:
                    self.set_typing(connection, cid, [], False)
        for connection in list(self.connections):
            if connection.user_id in removed:
                connection.denied_conversations.add(conversation_id)
                retained = []
                while not connection.queue.empty():
                    event = connection.queue.get_nowait()
                    if event.get("conversation_id") != conversation_id:
                        retained.append(event)
                for event in retained:
                    connection.queue.put_nowait(event)
            elif connection.user_id in added:
                connection.denied_conversations.discard(conversation_id)

    def typing_event(self, connection, conversation_id, recipients, active):
        self.emit(recipients, {"type": "typing.updated", "conversation_id": conversation_id,
            "occurred_at": now_utc().isoformat(), "payload": {"user_id": connection.user_id,
            "name": connection.name, "is_typing": active,
            "expires_at": (now_utc() + timedelta(seconds=5)).isoformat()}})

    def set_typing(self, connection, conversation_id, recipients, active):
        key = (connection, conversation_id)
        previous = self.typing.get(key)
        if active:
            now = time.monotonic()
            notify = previous is None or now - previous["notified"] >= 1
            self.typing[key] = {"expires": now + 5, "notified": now if notify else previous["notified"], "recipients": recipients}
            if notify:
                self.typing_event(connection, conversation_id, recipients, True)
        else:
            self.typing.pop(key, None)
            if previous and not any(c.user_id == connection.user_id and cid == conversation_id for c, cid in self.typing):
                self.typing_event(connection, conversation_id, previous["recipients"], False)

    def remove(self, connection):
        for c, cid in list(self.typing):
            if c is connection:
                self.set_typing(connection, cid, [], False)
        self.connections.discard(connection)
        if connection.writer:
            connection.writer.cancel()

    async def maintain(self):
        while True:
            await asyncio.sleep(1)
            for (connection, cid), value in list(self.typing.items()):
                if value["expires"] <= time.monotonic():
                    self.set_typing(connection, cid, [], False)


manager = ConnectionManager()
