# Single-origin production deployment - Phase 8B

Prepared and tested locally on 9 October 2026. Target: hosted verification by approximately 5:40 pm IST. No cloud resources, purchases, upgrades, commits or pushes were made in Phase 8B. This runbook supersedes the earlier Vercel/custom-domain proposal: no custom domain is required.

## Package and architecture

Deploy **one Railway Docker service**, using the repository root as its build context. The multi-stage Dockerfile builds Next.js standalone output with Node 24 and installs the existing backend requirements in Python 3.13.5. The runtime contains Node, Python/FastAPI and Nginx. No application dependency versions were upgraded.

Nginx is the sole public listener on **PORT**. Internal Next.js listens on 127.0.0.1:3000; FastAPI uses port 8000 and exactly one worker. Railway exposes only the proxy port. Keep exactly **one service replica**; the backend's connection registry is in memory.

| Public route | Destination |
| --- | --- |
| /api/v1/*, including /api/v1/ws | FastAPI; paths and query strings preserved |
| /health, /docs, /openapi.json | FastAPI |
| All other routes, Next assets and avatars | Next.js |

The proxy forwards Origin, Host and cookies without rewriting cookie domains. It explicitly forwards WebSocket Upgrade/Connection headers, disables proxy buffering and uses a 300-second read timeout; Uvicorn's protocol heartbeat keeps sockets alive. Railway terminates public TLS. [Nginx WebSocket documentation](https://nginx.org/en/docs/http/websocket.html), [Railway network limits](https://docs.railway.com/networking/public-networking/specs-and-limits).

The frontend Docker build sets **NEXT_PUBLIC_API_URL=same-origin**, so requests resolve against window.location.origin. The WebSocket URL derives the same host and chooses WSS for HTTPS. No public domain has to be embedded into the image, and runtime NEXT_PUBLIC values do not change the compiled bundle. The existing absolute API/WS environment settings remain supported for Windows development and other hosting. Docker-only standalone output does not change the normal Windows build/start commands.

Startup validates PORT, requires /data to be an actual mount, requires DATABASE_URL=sqlite:////data/signal.db, and resolves the browser origin from PUBLIC_ORIGIN or Railway's RAILWAY_PUBLIC_DOMAIN. It uses that same exact origin for FRONTEND_ORIGIN and WEBSOCKET_ORIGIN. SESSION_COOKIE_SECURE defaults to true in the image. The opaque cookie stays host-only, HttpOnly, SameSite=Lax and Path=/; HTTP and WSS authenticate against the same public host.

At runtime, the supervisor runs `python -m app.init_db --seed`, then starts the three services. Migration and seeding are additive/repeatable, not resets, and are not performed during image build. app.serve also performs the normal non-destructive migration check. SIGTERM stops child process groups, allows up to 20 seconds to exit, then terminates remaining processes. Any unexpected service-process exit stops the entire container with exit 1 so Railway can restart it. No backend replicas or automatic worker scaling are allowed.

## Local Docker preparation and inspection

Docker Desktop must show its Linux engine running. These commands run from the repository root; they do not mount backend/data or upload local environment files.

```powershell
Set-Location F:\signal-clone
docker version
docker build --progress plain -t signal-clone:phase8b .
docker volume create signal-phase8b-data
docker run -d --name signal-phase8b --mount source=signal-phase8b-data,target=/data -p 127.0.0.1:18080:8080 -p 127.0.0.1:18443:8443 -e PUBLIC_ORIGIN=https://localhost:18443 signal-clone:phase8b
.\backend\.venv\Scripts\python.exe -u deployment/tests/check_container.py
```

The named test container/volume already exist after this checkpoint: do not repeat `docker run` with the same name. The acceptance script adds a **test-only self-signed localhost certificate** inside that container, enables its extra TLS listener, runs HTTPS/WSS checks and restart tests, and leaves it running. The certificate/key are never copied into the production image or repository. Production TLS is provided by Railway; its public listener needs no self-signed certificate.

Review **https://localhost:18443** and **https://localhost:18443/health**. The self-signed certificate requires accepting the localhost certificate warning in each browser profile. HTTP localhost:18080/health is also available, but the test container's configured application origin is HTTPS localhost:18443. Do not test its login from the alternate HTTP origin. If you restart the container manually, rerun the acceptance script to restore its test TLS listener.

```powershell
docker logs --tail 60 signal-phase8b
docker inspect signal-phase8b --format '{{.State.Status}} {{.State.Health.Status}}'
docker stats --no-stream signal-phase8b
```

Backend development dependencies provide httpx/websockets for the test script. Existing Windows frontend/backend commands in README.md and DEVELOPMENT.md remain valid and unchanged. The acceptance script creates only fictional test data inside its dedicated Docker volume and keeps session tokens in memory. Do not delete the volume if you want to retain these inspection records.

## Railway settings - execute only after publication/deployment approval

1. Confirm account **trial eligibility, remaining credit and expiry** before deploying. Connect GitHub access to purvika621/signal-clone. A different Railway login email does not itself grant access to the GitHub repository. Do not purchase/upgrade without explicit approval.
2. After the deployment-package commit is approved and pushed, select repository **purvika621/signal-clone**, branch **main**. Pause autodeploys until settings/volume are ready if the dashboard has already created a draft/service. Merely opening Deploy Repo does not confirm a usable trial or disk.
3. Root Directory: repository root (**leave blank or use /**). Dockerfile path: **Dockerfile**. Build context: repository root. Use Railway's detected **Dockerfile builder**, not separate frontend/backend Railpack services. No custom Build Command, Start Command or Pre-deploy Command: the Dockerfile and CMD own these. If the UI asks for the Dockerfile path explicitly, enter Dockerfile. [Railway Dockerfiles](https://docs.railway.com/builds/dockerfiles).
4. Attach a **persistent volume at /data before any application deployment**. Trial volume limit is 0.5 GB, ample for this seeded text demo; paid plan limits differ. Do not rely on the ephemeral root filesystem, and do not set a build/pre-deploy SQLite seed command. Startup deliberately refuses an unmounted /data. [Volumes](https://docs.railway.com/volumes/reference).
5. Set the following service variables:

   | Variable | Value |
   | --- | --- |
   | PORT | 8080 (proxy/public port; startup also supports a different supplied valid port) |
   | DATABASE_URL | sqlite:////data/signal.db |
   | SESSION_COOKIE_SECURE | true |
   | MOCK_OTP | 123456 (public mocked verification, not a secret) |
   | SESSION_DAYS | 7 |
   | SQLITE_BUSY_TIMEOUT_MS | 5000 |
   | PUBLIC_ORIGIN | Actual generated HTTPS origin, such as https://SERVICE.up.railway.app; no trailing path |

   In Networking, **Generate Domain**, target port **8080**. Copy its actual HTTPS origin into PUBLIC_ORIGIN; no guessed URL. Alternatively, after Railway supplies RAILWAY_PUBLIC_DOMAIN for the generated domain, omit PUBLIC_ORIGIN and startup derives https:// plus that value. If generation happens after an initial start, redeploy/restart with the origin now available. [Public networking](https://docs.railway.com/networking/public-networking).

   FRONTEND_ORIGIN and WEBSOCKET_ORIGIN are set by the container supervisor from that resolved public origin, not separate competing origins. No custom domain, separate API URL, JWT secret or PUBLIC_WS secret is needed. Do not override the Docker build's NEXT_PUBLIC_API_URL/WS handling. PYTHON_VERSION is unnecessary: Python is pinned by the Dockerfile. Do not expose internal ports 3000/8000 as the domain target.

6. Replicas: **1**. Disable application sleeping/serverless mode if enabled; realtime clients need a continuously available service. Health Check Path: **/health**, startup timeout **120 seconds** if configurable. Use Railway's on-failure restart policy, bounded to approximately 10 retries if configurable, and inspect logs rather than hiding a persistent startup error.
7. Only with approval, deploy. Verify mount/startup logs, frontend HTML, /health and actual HTTPS origin. Verify the service image is within trial size/resource limits. Do not call deployment complete before browser checks and restart persistence pass.

## Costs and availability

Railway trial can cost **$0 out of pocket** while eligible credits remain: one-time $5 credit, up to 30 days, 1 GB RAM, 0.5 GB volume. Full-trial access requires Railway's account/GitHub verification; eligibility and remaining credit are **not yet confirmed**. Credits can run out sooner. Trial-created volumes are deleted 30 days after credit expiry unless retained by upgrading; this is not permanent free hosting. [Trial terms](https://docs.railway.com/pricing/free-trial).

Hobby costs **$5/month minimum**, with $5 included usage; additional usage is metered. Rates: RAM $10/GB-month, CPU $20/vCPU-month, volume $0.15/GB-month, egress $0.05/GB. Do not claim a fixed $5 total. Account plan and billing remain the owner's decision. [Pricing](https://docs.railway.com/pricing/plans).

If Railway eligibility prevents deployment, the same Docker package can run on one paid Render Docker Web Service with /data disk and PUBLIC_ORIGIN set to its generated onrender.com HTTPS origin. Render Starter plus 1 GB disk has a $7.25/month base cost before taxes/overages; memory must be checked. Render Free has no persistent disks. No alternative service or paid plan was created here.

## Checks completed and remaining

Local automated checks passed:

- Linux Docker image built, including Next.js standalone production compilation. Dedicated volume mounted; no local database or .env in the image.
- Existing **27 backend tests** passed; frontend type checking, lint, production build and messaging-state checks passed. Added same-origin HTTPS-to-WSS and local HTTP-to-WS assertions passed. Windows production build initially encountered sandbox spawn EPERM; unrestricted rerun passed.
- Through **Nginx with HTTPS/WSS**: frontend/assets/docs/health, secure host-only cookie flags, session restoration, authenticated sockets and wrong-origin rejection.
- Alex/Maya messages both ways, stable client-ID deduplication, real receipt events, unread clearing, typing expiry, offline replay/catch-up, membership enforcement and logout socket closure.
- New group persistence, duplicate-safe creation, admin permissions, add/remove, last-admin protection, group messaging/aggregate receipts and removed-member event/access revocation.
- Restart with the same volume retained row counts, created user/profile, existing sessions, messages, groups and receipts; authenticated WSS reconnected after restart. Backend child failure also stopped the container with exit 1 and subsequent startup retained data.
- Runtime production dependency audit reported no vulnerabilities; npm install reported dev-toolchain advisories. No dependency upgrades were made in this phase.
- Non-default public PORT=9090 served health and frontend through Nginx; SIGTERM shutdown exited cleanly with code 0. Startup without a /data mount was rejected. Image size was 374,766,314 bytes (approximately 357 MiB); measured idle test-container RAM was approximately 115 MiB, not a guarantee under load.

Browser automation was unavailable. Protocol tests are not browser rendering/interaction tests. The owner confirmed that the Phase 8B manual browser checks at https://localhost:18443 passed. **All hosted checks remain pending.** Railway account verification, real TLS/cookie behavior behind its edge, limits and persistence have not been tested yet.

Manual/hosted checklist:

1. Open the single public origin. On the local test URL only, accept the self-signed certificate warning. Check UI/assets and browser API/WS requests use that same host, with no localhost API destination in hosted JavaScript.
2. Alex in a normal window, Maya in Incognito: identifier alex/maya, public mock OTP 123456; complete profile if prompted. Refresh both; confirm session restoration. Verify HttpOnly/Secure/SameSite=Lax cookie and WSS upgrade 101.
3. Send both ways, type without sending, test multiline text, delivered/read states, inactive-chat unread/toast and clearing on visible/focused reading. Disconnect/reconnect and confirm missed messages appear once.
4. Kai in a third independent browser profile: create/rename group, add/remove Kai, verify all members receive messages and removed Kai loses access immediately. Logout and verify that session's socket closes.
5. Send a distinctive message and edit a profile/group; restart/redeploy the same hosted service with its volume; verify all persist and existing sessions recover. Retest group/admin and direct messaging.
6. Confirm credit remains and the hosted link is publicly accessible for evaluators. Add the actual verified hosted URL to README/submission only after hosted checks pass. GitHub: https://github.com/purvika621/signal-clone.

## Review and next approval

Application diff is limited to Docker-only standalone output, the explicit same-origin API option, WebSocket derivation sharing that option, and URL regression assertions. Backend feature code/models/contracts are unchanged. Packaging files are Dockerfile, .dockerignore, deployment/start.py, deployment/nginx.conf.template and deployment/tests/check_container.py. No commit or push has occurred in this phase.

After review, explicitly authorize committing/pushing the listed package and deploying to the confirmed trial (or approve the paid plan separately). Then inspect `git diff`, stage only those files plus this runbook/README changes, commit `Add single-origin production deployment package`, and normal-push main to origin. Do not force-push. Configure the volume/domain/variables above and perform hosted acceptance checks before submission.
