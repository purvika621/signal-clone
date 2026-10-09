"""Single-origin container supervisor; a failed child stops the whole service."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from urllib.parse import urlsplit

children: list[subprocess.Popen] = []
stopping = False


def stop(_signal=None, _frame=None):
    global stopping
    stopping = True
    for child in children:
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)


def main():
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    port = int(os.environ.get("PORT", "8080"))
    if not 1 <= port <= 65535 or port in {3000, 8000}:
        raise ValueError("Public PORT must be valid and distinct from internal ports 3000/8000")
    if not os.path.ismount("/data"):
        raise RuntimeError("Mount a persistent volume at /data; refusing ephemeral SQLite storage")
    if os.environ.get("DATABASE_URL") != "sqlite:////data/signal.db":
        raise ValueError("Container DATABASE_URL must be sqlite:////data/signal.db")
    domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
    origin = os.environ.get("PUBLIC_ORIGIN") or (f"https://{domain}" if domain else None)
    if not origin:
        raise ValueError("Set PUBLIC_ORIGIN, or generate a Railway domain before starting")
    parsed = urlsplit(origin)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("PUBLIC_ORIGIN must be a single HTTP(S) origin")
    origin = origin.rstrip("/")
    backend_env = {**os.environ, "FRONTEND_ORIGIN": origin, "WEBSOCKET_ORIGIN": origin, "PORT": "8000",
                   "FORWARDED_ALLOW_IPS": "127.0.0.1"}
    config = Path("/app/deployment/nginx.conf.template").read_text().replace("@PORT@", str(port))
    Path("/tmp/signal-nginx.conf").write_text(config)
    subprocess.run(["nginx", "-t", "-c", "/tmp/signal-nginx.conf"], check=True)
    # Runtime volume is present here; neither migration nor seed runs during build.
    init = subprocess.Popen([sys.executable, "-m", "app.init_db", "--seed"], cwd="/app/backend", env=backend_env, start_new_session=True)
    children.append(init)
    if init.wait() != 0 or stopping:
        return 1
    commands = [
        ([sys.executable, "-m", "app.serve"], "/app/backend", backend_env),
        (["node", "server.js"], "/app/frontend", {**os.environ, "PORT": "3000", "HOSTNAME": "127.0.0.1"}),
        (["nginx", "-c", "/tmp/signal-nginx.conf", "-g", "daemon off;"], "/app", os.environ.copy()),
    ]
    for command, cwd, env in commands:
        if stopping:
            return 0
        children.append(subprocess.Popen(command, cwd=cwd, env=env, start_new_session=True))
    while not stopping:
        for child in children[1:]:
            if child.poll() is not None:
                print(f"Service process {child.args[0]} exited ({child.returncode}); stopping container", flush=True)
                return 1
        time.sleep(0.2)
    return 0


if __name__ == "__main__":
    result = 1
    try:
        result = main()
    finally:
        stop()
        deadline = time.monotonic() + 20
        for child in children:
            try:
                child.wait(timeout=max(0.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
    sys.exit(result)
