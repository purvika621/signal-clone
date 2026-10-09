FROM node:24-bookworm-slim AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1 DOCKER_BUILD=true NEXT_PUBLIC_API_URL=same-origin
RUN npm run build

FROM python:3.13.5-slim-bookworm AS backend-build
WORKDIR /build
COPY backend/requirements.txt ./
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

FROM python:3.13.5-slim-bookworm AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends nginx ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=frontend-build /usr/local/bin/node /usr/local/bin/node
COPY --from=backend-build /opt/venv /opt/venv
WORKDIR /app
COPY --from=frontend-build /build/frontend/.next/standalone /app/frontend
COPY --from=frontend-build /build/frontend/.next/static /app/frontend/.next/static
COPY --from=frontend-build /build/frontend/public /app/frontend/public
COPY backend/app /app/backend/app
COPY backend/migrations /app/backend/migrations
COPY backend/alembic.ini /app/backend/alembic.ini
COPY deployment/start.py deployment/nginx.conf.template /app/deployment/
ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    NEXT_TELEMETRY_DISABLED=1 DATABASE_URL=sqlite:////data/signal.db SESSION_COOKIE_SECURE=true PORT=8080
EXPOSE 8080
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8080')+'/health',timeout=4)"
CMD ["python", "/app/deployment/start.py"]
