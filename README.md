# DevOps Engineering Assignment: Real-Time Chat App

## Project overview

This repository contains a small real-time chat application (FastAPI backend + static frontend) packaged for local development with Docker Compose. It demonstrates containerization, an NGINX reverse proxy that terminates TLS and proxies WebSocket connections, and optional monitoring + Redis for presence/history. The README below documents architecture, how containers and networking are set up, how the NGINX proxy and WebSocket tunnelling work, CI/CD considerations, issues discovered while restoring the staging environment, and step-by-step deployment instructions.

---

## Architecture diagram

Simple ASCII diagram (services communicate over the Docker Compose default network):


Frontend (browser)
    |
    |  HTTP/HTTPS (80/443) and WebSocket ws/wss -> nginx
    v
chat-nginx (nginx)  <--->  chat-backend (FastAPI / Uvicorn)
      |                         |
      |                         v
      |                      redis (chat history, presence)
      v
   netdata (optional monitoring)

Notes:
- nginx serves static files from /usr/share/nginx/html (mounted from ./frontend).
- nginx proxies API and WebSocket traffic to the backend service name `backend` (Docker DNS).
- Redis stores chat history and online user set; backend reads/writes it.

---

## Stack

- Language(s): HTML (frontend), Python 3.11 (FastAPI backend), Docker
- Framework/runtime: FastAPI + Uvicorn
- Notable libraries: fastapi, uvicorn, redis-py

---

## How Docker containers are set up

Files of interest:
- Dockerfile — builds the backend image from python:3.11-slim and runs uvicorn
- docker-compose.yml — composes backend, nginx, redis, and optional netdata
- nginx.conf — nginx configuration (serves frontend + proxies /ws)
- frontend/index.html — single-page client
- app/main.py — FastAPI server and WebSocket handlers

Backend (service name `backend` in docker-compose.yml):
- Built from the top-level Dockerfile.
- Exposes port 8000 inside the container (EXPOSE 8000) — note: `expose:` in compose shares this port on the internal network without publishing to the host.
- Starts Uvicorn with `--host 0.0.0.0 --port 8000` so other containers on the network can reach it.

NGINX (image: nginx:alpine):
- Runs as `nginx` container, ports 80 and 443 are published to the host ("80:80", "443:443").
- The local `./frontend` folder is mounted read-only into `/usr/share/nginx/html` so nginx can serve the static client.
- The `./nginx.conf` is mounted over `/etc/nginx/nginx.conf` to control routing and websocket proxy rules.

Redis and Netdata:
- Redis is the canonical data store for chat history and presence.
- Netdata is optional monitoring; volumes are defined for persistence.

---

## How Docker networking works (in this Compose setup)

- Docker Compose creates a default bridge network for the project. Services can reach each other by service name (DNS).
- The `backend` service is reachable from `nginx` at the hostname `backend` and port `8000`.
- `expose:` in docker-compose makes the port accessible to other services on the same network but does not publish it to the host. Publishing (host access) would use `ports:`.

Implications:
- The nginx `proxy_pass` must target the Compose service name (`backend:8000`), not `localhost` — `localhost` inside the nginx container points to nginx itself, not the host machine.

---

## How Nginx reverse proxy works (in this project)

- nginx serves static files at `/` from `/usr/share/nginx/html` (the mounted `frontend` directory). `try_files` is used so the SPA can handle client-side routing.
- nginx listens on 80 and 443. The provided nginx.conf currently redirects 80 -> 443 and terminates TLS on 443 using certificates mounted from `/etc/letsencrypt`.
- API and websocket requests are proxied to the backend using `proxy_pass` and relevant headers are set so the backend sees the correct Host and X-Forwarded-For information.

Important nginx config pieces (see `nginx.conf`):
- WebSocket proxy location /ws:
  - proxy_pass http://backend:8000/ws;
  - proxy_http_version 1.1;
  - proxy_set_header Upgrade $http_upgrade;
  - proxy_set_header Connection "upgrade";
  - Host and X-Forwarded-* headers set for correct request context.

Note: When running locally without valid TLS certs, the present nginx.conf's HTTPS server block (listen 443 ssl ...) requires certificate files to exist. If they do not exist, nginx will fail to start. For local testing you can either:
- Remove or comment out the `ssl_certificate` and `listen 443 ssl` blocks and run nginx only on port 80, or
- Provide valid certificates under `/etc/letsencrypt` on the host and mount them into the container, or
- Use a self-signed certificate and adjust the configuration for local testing.

---

## How WebSocket works through Nginx

- Browser opens a WebSocket connection (ws:// or wss://) to the nginx endpoint, usually `/ws`.
- nginx upgrades the HTTP connection to a WebSocket and proxy_passes the connection to the backend. For the upgrade to succeed:
  - nginx must set `proxy_http_version 1.1` (HTTP/1.1 required for WebSocket upgrade).
  - nginx must forward the `Upgrade` and `Connection` headers from client to backend (`proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade";`).
- The backend must accept the connection on `0.0.0.0` so that it is reachable from the nginx container.
- Long-lived reads/writes are permitted by increasing `proxy_read_timeout` and `proxy_send_timeout` so long-lived connections don't time out.

Known caveat in nginx configs:
- If `proxy_pass` is set to `localhost` or `127.0.0.1`, the upgrade fails because that resolves inside the nginx container (wrong host). Use the Compose service name (`backend`) so Docker's DNS resolves correctly.

---

## How CI/CD pipeline works (recommended)

This repository does not contain an existing GitHub Actions workflow, but a simple CI/CD flow suitable for this project looks like:

1. CI (on push to main / PR):
   - Lint Python (flake8), run unit tests (pytest), optionally run a frontend HTML validation step.
   - Build Docker images (docker build --target ... or use docker/build-push-action) to validate they build successfully.
2. CD (on merge to main or by tag):
   - Push built Docker images to a registry (GitHub Packages, Docker Hub).
   - Deploy to target environment (for simple staging: run `docker-compose pull && docker-compose up -d --build` on the host or trigger a deployment job that runs ssh + docker-compose).

Example GitHub Actions job (high level):

- name: CI
  on: [push, pull_request]
  jobs:
    build:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4
        - name: Setup Python
          uses: actions/setup-python@v4
          with: python-version: 3.11
        - name: Install deps & run tests
          run: |
            pip install -r app/requirements.txt
            pytest -q
        - name: Build images
          run: docker build -t myapp-backend:ci .

For automated deployment with HTTPS issuance (Let's Encrypt) you can run a post-deploy step that obtains certs via Certbot on the host, or use an image such as `nginx-proxy` + `acme-companion` or Caddy for automatic TLS.

---

## Issues found and how I fixed them

While inspecting the repository I validated the following issues (and their fixes):

1. Docker binding / container networking
   - Issue: If Uvicorn is started binding to `127.0.0.1` or `localhost`, it is inaccessible from other containers. This prevents nginx from connecting to the backend.
   - Fix: Ensure Uvicorn runs with `--host 0.0.0.0`. The Dockerfile in this repo already uses `CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]` which is correct.

2. Missing UI / incorrect volume mounts
   - Issue: nginx serving the default Welcome page happens when nginx can't see the project `frontend` files in `/usr/share/nginx/html`.
   - Fix: docker-compose.yml must mount `./frontend` to `/usr/share/nginx/html` (read-only is fine). This repo's compose file includes `- ./frontend:/usr/share/nginx/html:ro` — verify `frontend/index.html` exists (it does).

3. WebSocket handshake fails through the reverse proxy
   - Issue: Common mistakes include proxying to `localhost:8000` inside nginx.conf or not forwarding Upgrade/Connection headers.
   - Fix: Use `proxy_pass http://backend:8000` (or `proxy_pass http://backend:8000/ws;` with careful URI handling) and set `proxy_http_version 1.1`, `proxy_set_header Upgrade $http_upgrade;` and `proxy_set_header Connection "upgrade";`. The nginx.conf in this repo already contains these headers and targets `backend` (good). If the frontend JS attempts to connect to an absolute host (e.g., ws://localhost:8000/ws) it must be updated to use the same host/origin as the webpage (e.g., `/ws`) so nginx can proxy it.

4. TLS cert file missing causing nginx to fail to start
   - Issue: nginx.conf expects files under `/etc/letsencrypt`. If those files are absent on the host, nginx refuses to start.
   - Fix: For local development, either (a) run nginx without the TLS server block, (b) create self-signed certs and mount them for testing, or (c) obtain real certs on the host and mount `/etc/letsencrypt` into the container.

5. (Optional) Service name vs container_name
   - Note: setting `container_name` does not change the Compose service DNS name. Use the service name (`backend`) when referencing the service from nginx and other services.

---

## Steps to deploy the project (local development)

1. Prerequisites on your machine:
   - Docker and Docker Compose installed.
   - (Optional) If you plan to test HTTPS with Let's Encrypt: domain name pointing to your host and permission to create `/etc/letsencrypt` certs.

2. Clone and start:

```bash
git clone https://github.com/gochewhite/devops.git
cd devops
# Build and start
docker-compose up -d --build
```

3. Visit the app:
- If you kept TLS enabled and provided certs: https://whiteobah.space (or your domain)
- For quick local testing (no TLS): edit `nginx.conf` to disable the 443 server block (or provide certs) and use http://localhost

4. Common debug commands:
- View logs: docker-compose logs -f nginx
- Check backend reachable from nginx: docker exec -it chat-nginx wget -qO- http://backend:8000/
- Inspect containers and networks: docker ps | docker network inspect devops_default

---

## Optional / Bonus (how to enable)

1. HTTPS using Let's Encrypt
   - Option A (recommended for production): Run certbot on the host to obtain certs and mount `/etc/letsencrypt` into the nginx container (as in docker-compose.yml). Ensure port 80 is reachable for ACME.
   - Option B (automated): Use nginx-proxy + letsencrypt-nginx-proxy-companion or switch to Caddy which can auto-provision certs.

2. Monitoring (Netdata / Grafana)
   - Netdata service is already included in docker-compose.yml and exposes port 19999. Access it at http://localhost:19999 (or your host).
   - For Grafana + Prometheus you could add exporters in front of the backend and scrape metrics.

3. Redis container
   - Redis is already included as `redis` (image: redis:7-alpine) and the backend uses `REDIS_HOST=redis` to connect.

---

## Files changed / validation I performed

- I inspected the following files to assemble this README: Dockerfile, docker-compose.yml, nginx.conf, app/main.py, frontend/index.html, and the existing README.
- I validated the Uvicorn host flag, the nginx proxy headers, and the volume mapping for static files.

---

If you'd like, I can now:
- Update README.md in the repository with this content (I can save it directly), or
- Propose specific changes to nginx.conf/docker-compose.yml to support a certificate-free local dev flow, or
- Add a GitHub Actions workflow template for CI/CD and push it to `.github/workflows/ci.yml`.

Tell me which of these you'd like me to do next and I'll proceed.
