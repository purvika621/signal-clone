import pytest
from pydantic import ValidationError
from app.config import Settings
from app.config import settings as live_settings
from test_realtime import live_server, event


def test_explicit_production_origins_and_persistent_path():
    settings = Settings(_env_file=None, database_url="sqlite:////data/signal.db",
        frontend_origin="https://app.example.invalid/", websocket_origin="https://app.example.invalid/",
        session_cookie_secure=True, port=8080)
    assert settings.frontend_origin == settings.websocket_origin == "https://app.example.invalid"
    assert settings.database_url == "sqlite:////data/signal.db"
    assert settings.port == 8080 and settings.session_cookie_secure


@pytest.mark.parametrize("origin", ["*", "wss://app.example.invalid", "https://app.example.invalid/path", "https://app.example.invalid?query=1"])
def test_invalid_websocket_origins_rejected(origin):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, websocket_origin=origin)


def test_configured_socket_origin_overrides_http_origin(live_server, monkeypatch):
    import asyncio
    import httpx
    from websockets.asyncio.client import connect
    from websockets.exceptions import InvalidStatus

    base, socket_url, _ = live_server
    socket_origin = "https://frontend.example.invalid"
    monkeypatch.setattr(live_settings, "websocket_origin", socket_origin)
    async def verify():
        async with httpx.AsyncClient(base_url=base, headers={"Origin": "http://localhost:3000"}) as client:
            result = await client.post("/api/v1/auth/verify", json={"identifier": "alex", "otp": "123456"})
            assert result.status_code == 200
            headers = {"Cookie": f'signal_session={client.cookies.get("signal_session")}'}
            with pytest.raises(InvalidStatus):
                async with connect(socket_url, origin="http://localhost:3000", additional_headers=headers):
                    pass
            async with connect(socket_url, origin=socket_origin, additional_headers=headers) as ws:
                ready = await event(ws, lambda value: value["type"] == "session.ready")
                assert ready["payload"]["user_id"] == result.json()["user"]["id"]
    asyncio.run(verify())
