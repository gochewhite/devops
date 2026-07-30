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

(see appended detailed section — contains root cause, fixes, and verification steps for each issue encountered during rollout)

---

## Repository contents and bonus components

The repository already contains the following optional/bonus components:

- HTTPS: `nginx-ssl.conf` and `docker-compose.prod.yml` reference Let's Encrypt mounts for production.
- Monitoring: `netdata` service is included in `docker-compose.yml` and exposes port 19999.
- Redis: `redis` service is present and used by the backend for chat history and presence.
- Infrastructure as Code: a `terraform/` directory exists with TF modules to provision AWS resources.

Caveats found in the repo:
- The `terraform/` directory currently contains generated state and a binary artifact that should not be tracked (`terraform.tfstate`, `terraform.tfstate.backup`, and an embedded Terraform binary). See cleanup steps below.

---

## Cleanup / housekeeping (required actions)

The repository contains generated Terraform artifacts that must be removed and ignored to keep the repo portable and within Git limits. Run the following on your workstation (one-time):

```bash
# from repo root
# remove large or generated terraform artifacts from git history (local cleanup)
git rm -r --cached terraform/.terraform || true
git rm --cached terraform/terraform.tfstate terraform/terraform.tfstate.backup || true
git rm --cached terraform/terraform_*.zip || true
# commit the removal and add .gitignore
git add .gitignore
git commit -m "chore: remove terraform cache and provider artifacts from repo and ignore them"
# push to origin
git push origin main
```

I added a helper script `scripts/cleanup-terraform.sh` you can run locally to perform the above steps automatically (it requires your local git credentials).

---

## Recommended follow-ups

- Add a `healthcheck` for the backend service in `docker-compose.yml` so orchestrators can fail fast.
- Implement a small GitHub Actions workflow that builds and validates `docker compose up` on PRs.
- Move sensitive or environment-specific configuration into a `config` directory and load via env files that are not checked in.

---

## Operational summary

The deployment process prioritizes reproducibility and operational clarity. With the README additions and the housekeeping steps above, another engineer should be able to:
- run the stack locally for review,
- perform reproducible production deployments via GitHub Actions,
- and maintain the infrastructure using Terraform after cleaning the repository state.
