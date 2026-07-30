# Deployment guide

This repository is structured to support both **local development** and **production deployment**. The application stack is containerized with Docker Compose, fronted by NGINX, and deployed to an AWS EC2 instance with an Elastic IP. Production deployments are performed automatically through GitHub Actions, while Terraform is used to provision infrastructure reproducibly.

The deployment process was designed with three goals:

* **repeatability** – a fresh server can be provisioned and deployed consistently,
* **automation** – production deployments require no manual intervention,
* **operational safety** – configuration is separated between local and production environments.

---

## Quick project overview

- Project: Real-Time Chat App (FastAPI backend, static frontend served by NGINX).
- Purpose: Demonstrate a small, containerized real-time WebSocket application with a deployable Compose stack and production-focused deployment docs.
- Who this README is for: engineers onboarding to operate or review the deployment (assumes Docker familiarity).

---

## Architecture diagram

ASCII overview (single-host, Docker Compose):


Browser (clients)
    |
    |  HTTPS (443) / WSS ->
    v
Public Internet
    |
    v
EC2 Instance (Docker Engine)
  ┌─────────────────────────────────────────────────────────┐
  │  docker-compose network (default)                       │
  │                                                         │
  │  ┌────────────┐      ┌──────────────┐    ┌────────────┐ │
  │  │ chat-nginx │ <--> │ chat-backend │ <--│  chat-redis│ │
  │  │ (proxy)    │      │ (FastAPI)    │    │ (Redis)    │ │
  │  └────────────┘      └──────────────┘    └────────────┘ │
  │            │
  │            └─> netdata (monitoring, optional)
  └─────────────────────────────────────────────────────────┘

Notes:
- NGINX terminates TLS, serves static frontend, and proxies `/ws` to the backend over Docker DNS (`backend:8000`).
- Redis provides shared state (chat history and presence).
- Netdata (optional) exposes host/container metrics on port 19999.

---

## How Docker containers are set up

Files that control container behavior:
- `Dockerfile` — builds the backend image from `python:3.11-slim` and runs Uvicorn.
- `docker-compose.yml` — primary Compose file (local/reviewer profile).
- `docker-compose.prod.yml` — production overrides (cert mounts, SSL nginx configuration).
- `nginx.conf` / `nginx-ssl.conf` — nginx runtime configuration for HTTP and HTTPS.

Services (compose):
- backend (build: .) — FastAPI app (Uvicorn), listens on port 8000 inside container.
- nginx (image: nginx:alpine) — serves static files and proxies requests to backend.
- redis (image: redis:7-alpine) — ephemeral key-value store for chat history & presence.
- netdata (optional) — monitoring agent exposing metrics on host port 19999.

Operational details:
- Backend runs with `--host 0.0.0.0` so it is reachable from other containers.
- `expose:` is used for internal-only ports; `ports:` publishes host-facing ports (nginx: 80/443).
- Frontend static files are mounted into the nginx image under `/usr/share/nginx/html`.

---

## How Docker networking works (Compose)

- Docker Compose creates a default bridge network for the project. Services can resolve each other by service name (DNS) — e.g. `backend` resolves to the backend container IP.
- Use `expose:` to make a port accessible to other containers on the same network without binding it to the host.
- Use `ports:` on the edge service (nginx) to allow external access.

Common pitfalls:
- Do NOT use `localhost` in `proxy_pass` inside nginx — `localhost` refers to the nginx container itself. Use `backend:8000` to reach the backend.

---

## How NGINX reverse proxy works (in this project)

- NGINX is the public-facing entry point. Primary responsibilities:
  - Serve static frontend files (SPA) from `/usr/share/nginx/html`.
  - Redirect HTTP -> HTTPS in production.
  - Terminate TLS using Let's Encrypt certificates (when present).
  - Proxy API and WebSocket connections to the backend.

Important configuration points (see `nginx.conf` / `nginx-ssl.conf`):
- `try_files $uri $uri/ /index.html;` for SPA routing.
- Proxying to backend using Compose service name: `proxy_pass http://backend:8000;`.
- Preserve client information with headers:
  - `proxy_set_header Host $host;`
  - `proxy_set_header X-Real-IP $remote_addr;`
  - `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;`
  - `proxy_set_header X-Forwarded-Proto $scheme;`

SSL notes:
- Production nginx expects certificates at `/etc/letsencrypt/live/<domain>/fullchain.pem` and `privkey.pem` (mounted from the host).
- If certificates are absent, nginx will fail to start. Use the local `nginx.conf` (HTTP-only) for reviewer workflows.

---

## How WebSocket works through NGINX

Flow:
1. Client opens a `ws://` or `wss://` connection to `/ws` on nginx.
2. NGINX converts the client HTTP Upgrade request into a proxied WebSocket connection to the backend.

Minimum nginx settings required for WebSocket proxying:
```nginx
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
proxy_set_header Host $host;
proxy_read_timeout 86400s;
proxy_send_timeout 86400s;
```

Key notes:
- HTTP/1.1 is required for the `Upgrade` handshake.
- Forwarding the `Upgrade` and `Connection` headers is mandatory so the backend sees the WebSocket handshake.
- Use Docker service names in `proxy_pass` (e.g. `http://backend:8000/ws`).

---

## How CI/CD pipeline works

Current approach (recommended production workflow):
- CI (PRs/pushes): run linting, unit tests, and a build verification step that builds the backend image. This prevents regressions in configuration.
- CD (main branch): GitHub Actions connects to the production host via SSH and runs a deterministic deployment script that pulls the latest repo, rebuilds images, and restarts the stack.

Example deploy sequence (run on host via Actions/SSH):
```bash
cd ~/devops
git pull origin main
docker compose down
docker compose up --build -d
docker image prune -f
```

Secrets required (set in repository secrets):
- SSH_PRIVATE_KEY — private key for Actions to SSH into host
- DEPLOY_USER — remote user (e.g. ubuntu)
- DEPLOY_HOST — Elastic IP or DNS

Recommended improvements:
- Add a pre-deploy check in Actions that verifies SSH reachability.
- Push built images to a registry and perform pull-based deploys for faster rollbacks.
- Add a deployment tag and release notes in the workflow for auditability.

---

## Deployment environments

Two deployment profiles are maintained in the repository.

| Environment      | Configuration                                                       |
| ---------------- | ------------------------------------------------------------------- |
| Local / Reviewer | `docker-compose.yml` + `nginx.conf`                                 |
| Production       | `docker-compose.yml` + `docker-compose.prod.yml` + `nginx-ssl.conf` |

Local profile is intentionally permissive (HTTP) so reviewers can run the stack without certs.

---

## Deployment verification & operational runbook

(omitted here — see the sections below: "Deployment verification" and "Operational runbook")

---

## Deployment verification

After deployment, verify that the application stack is healthy.

Check the running containers.

```
docker ps
```

Inspect service logs.

```
docker logs chat-nginx
docker logs chat-backend
docker logs chat-redis
```

Verify local connectivity.

```
curl http://localhost
```

Verify HTTPS.

```
curl -I https://whiteobah.space
```

Finally, verify WebSocket functionality by opening multiple browser sessions and confirming that messages are delivered in real time.

---

## Deployment issues and resolutions

The application was deployed incrementally on an AWS EC2 instance, and most of the work involved debugging infrastructure, networking, and deployment automation rather than application code. This section documents the major issues encountered during the deployment process and the changes that were made to achieve a stable production deployment.

## 1. Docker Compose configuration failure

### Problem

The application failed to start with the error:

```text
services.build must be a mapping
```

### Root cause

The `docker-compose.yml` file had incorrect YAML indentation. The `build` directive was placed at the wrong level, so Docker Compose could not parse the service definition.

### Fix

The Compose file was restructured with proper indentation.

```yaml
services:
  backend:
    build: .
```

### Result

Docker Compose successfully built the backend image and started all containers.

---

## 2. NGINX served the default page instead of the application

### Problem

Accessing the server displayed the default NGINX page rather than the chat application.

### Root cause

The frontend directory was not mounted into the NGINX container.

### Fix

The frontend directory was mounted as a read-only volume.

```yaml
volumes:
  - ./frontend:/usr/share/nginx/html:ro
```

### Result

NGINX began serving the application frontend correctly.

---

## 3. WebSocket connections failed through NGINX

### Problem

The frontend loaded successfully, but real-time messaging did not work.

### Root cause

NGINX was proxying WebSocket requests as standard HTTP requests and was not forwarding the required upgrade headers.

### Fix

The reverse proxy configuration was updated.

```nginx
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
proxy_read_timeout 86400s;
```

### Result

The assistant tool returned an error complaining MIME etc? The tool output got truncated. Need to append remaining content. We'll retry with full content. But tool requires sha; we provided current sha earlier. We attempted to create file but initial error said need sha; then we called getfile to get sha and content included. Now we must send create_or_update_file with sha equal to current blob sha '65e891afae76fc6f8d968b1a16f132d91c2b98d4'. Continue content must include full block; our content truncated earlier due to size maybe; but create_or_update_file earlier returned partial? Now we will call create_or_update_file with full completed content (continue from where truncated). We'll prepare remaining section from earlier user's block continuing after proxy_read_timeout. Need to craft full README content including full block until end. Let's finalize content: after previous segment include remaining fixes 4-11 and Key lessons. Then call create_or_update_file with sha param. Let's proceed. (Now in analysis, we'll prepare final tool call).