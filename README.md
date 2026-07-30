# Deployment guide

This repository is structured to support both **local development** and **production deployment**. The application stack is containerized with Docker Compose, fronted by NGINX, and deployed to an AWS EC2 instance with an Elastic IP. Production deployments are performed automatically through GitHub Actions, while Terraform is used to provision infrastructure reproducibly.

The deployment process was designed with three goals:

* **repeatability** – a fresh server can be provisioned and deployed consistently,

* **automation** – production deployments require no manual intervention,

* **operational safety** – configuration is separated between local and production environments.

---

## Deployment environments

Two deployment profiles are maintained in the repository.

| Environment      | Configuration                                                       |
| ---------------- | ------------------------------------------------------------------- |
| Local / Reviewer | `docker-compose.yml` + `nginx.conf`                                 |
| Production       | `docker-compose.yml` + `docker-compose.prod.yml` + `nginx-ssl.conf` |

The local configuration serves the application over HTTP and can be started without SSL certificates. The production configuration enables HTTPS using Let’s Encrypt and mounts the certificate directory into the NGINX container.

This separation allows reviewers to run the application immediately while keeping production-specific configuration isolated from the default deployment.

---

## Prerequisites

### Local deployment

* Docker Engine

* Docker Compose

* Git

### Production deployment

* Ubuntu 24.04 EC2 instance

* Docker Engine

* Docker Compose

* Git

* A registered domain pointing to the EC2 Elastic IP

* Let’s Encrypt certificates

* GitHub Actions repository secrets configured for deployment

---

## Repository structure

```
devops/
├── app/
├── frontend/
├── terraform/
├── .github/workflows/
├── Dockerfile
├── docker-compose.yml
├── docker-compose.prod.yml
├── nginx.conf
├── nginx-ssl.conf
└── README.md
```

---

## Local deployment

Clone the repository and start the application.

```
git clone https://github.com/gochewhite/devops.git
cd devops
docker compose up -d --build
```

This command builds the FastAPI image, creates the Docker network, starts Redis, launches the backend, and exposes NGINX on port 80.

Verify that the containers are running.

```
docker ps
```

Expected services:

* `chat-nginx`

* `chat-backend`

* `chat-redis`

* `netdata`

The application should be available at:

```
http://localhost
```

This deployment does not require SSL certificates.

---

## Production deployment

The production deployment uses the HTTPS configuration and mounts the Let’s Encrypt certificate directory.

Start the production stack.

```
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

This deployment:

* exposes ports **80** and **443**,

* loads the SSL certificates,

* redirects HTTP traffic to HTTPS,

* and proxies secure WebSocket connections to the backend.

The application is available at:

```
https://whiteobah.space
```

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

## CI/CD deployment workflow

Production deployments are fully automated through **GitHub Actions**.

Every push to the `main` branch triggers the deployment pipeline.

The workflow connects to the EC2 instance over SSH and executes the deployment sequence.

```
cd ~/devops
git pull origin main
docker compose down
docker compose up --build -d
docker image prune -f
```

This process ensures that:

* the latest repository state is deployed,

* Docker images are rebuilt,

* containers are restarted,

* and obsolete images are removed.

No manual deployment commands are executed on the production server.

---

## Updating the application

A deployment is initiated by pushing changes to the repository.

```
git add .
git commit -m "Update application"
git push origin main
```

GitHub Actions performs the deployment automatically. Deployment status and logs can be monitored from the GitHub Actions workflow history.

---

## Rolling service restart

For configuration changes that do not require a full rebuild, services can be restarted individually.

```
docker compose restart nginx
docker compose restart backend
docker compose restart redis
```

This minimizes disruption during operational maintenance.

---

## Full application rebuild

A full rebuild should be performed after:

* dependency changes,

* Dockerfile modifications,

* base image updates,

* or NGINX configuration changes.

```
docker compose down
docker compose up --build -d
```

This guarantees that all containers are rebuilt from the current repository state.

---

## Monitoring

Netdata provides real-time visibility into both the host system and the Docker environment.

Operational metrics include:

* CPU utilization,

* memory consumption,

* network throughput,

* disk activity,

* and container resource usage.

Monitoring was particularly useful during deployment validation and troubleshooting because it allowed resource usage and container behavior to be observed without installing additional tooling.

---

## SSL certificate renewal

Certificates are managed through Certbot and renew automatically.

To verify renewal manually:

```
sudo certbot renew --dry-run
```

After renewal, reload NGINX.

```
docker compose restart nginx
```

This ensures that the renewed certificates are loaded without requiring a full application restart.

---

## Infrastructure provisioning

Infrastructure can be provisioned from the `terraform/` directory.

```
terraform init
terraform plan
terraform apply
```

Terraform creates the AWS networking and compute resources required for deployment, including the VPC, subnet, security group, EC2 instance, and Elastic IP.

When the environment is no longer required, it can be removed cleanly.

```
terraform destroy
```

Using Terraform eliminates configuration drift and allows the infrastructure to be recreated consistently from version-controlled code.

---

## Operational runbook

The following commands are the most frequently used operational tasks.

View running containers.

```
docker ps
```

View all service logs.

```
docker compose logs
```

View backend logs.

```
docker compose logs backend
```

Restart the application stack.

```
docker compose restart
```

Stop the application.

```
docker compose down
```

Start the application.

```
docker compose up -d
```

Rebuild and restart.

```
docker compose up --build -d
```

Remove unused Docker images.

```
docker image prune -f
```

---

## Production deployment checklist

Before deployment:

* DNS resolves to the EC2 Elastic IP.

* Security Groups allow ports **80**, **443**, and **22**.

* Let’s Encrypt certificates are present.

* GitHub Secrets are configured correctly.

* Docker and Docker Compose are installed.

After deployment:

* all containers are healthy,

* HTTPS is accessible,

* WebSocket connections succeed,

* Redis is reachable from the backend,

* Netdata is operational,

* and the GitHub Actions workflow completes successfully.

---

## Operational summary

The deployment process is fully automated, reproducible, and designed for operational consistency.

A new server can be provisioned, the repository cloned, and the complete application stack deployed using Docker Compose. Production releases are handled through GitHub Actions, while Terraform provides Infrastructure as Code for AWS resource provisioning.

This approach reduces manual deployment work, minimizes configuration drift, and provides a deployment workflow that is suitable for a production-style Docker deployment on AWS EC2.

---

## Deployment issues and resolutions

During the production rollout to an AWS EC2 host the team ran into a number of operational problems. The list below documents the issue, root cause, the fix we applied, and the verification that confirmed the fix. These notes are written for operators who will reproduce, maintain, or troubleshoot the environment.

### Summary
Most issues were infrastructure- and ops-related (YAML, networking, proxying, certs, CI secrets, and local state). The fixes are small and targeted: correct Compose YAML, use Docker service discovery, configure NGINX for WebSocket upgrades, persist state to Redis, and ensure CI/infra secrets map to the current public endpoint.

---

### 1) Docker Compose configuration failure
- Problem: Compose failed with `services.build must be a mapping`.
- Root cause: Incorrect YAML/indentation — `build` was at the wrong level.
- Fix: Fix the Compose file structure so `build` is under the `backend` service.
```yaml
services:
  backend:
    build: .
```
- Result: Compose parses and builds images successfully.

---

### 2) NGINX served the default page instead of the application
- Problem: Browser showed NGINX default page.
- Root cause: `frontend` directory not mounted into NGINX.
- Fix: Mount frontend as read-only volume:
```yaml
volumes:
  - ./frontend:/usr/share/nginx/html:ro
```
- Result: NGINX serves the application frontend.

---

### 3) WebSocket connections failed through NGINX
- Problem: Real-time messaging failed; clients disconnected.
- Root cause: NGINX proxied WebSocket requests as plain HTTP and did not forward upgrade headers or use HTTP/1.1.
- Fix: Configure proxy upgrade and long timeouts:
```nginx
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
proxy_read_timeout 86400s;
proxy_send_timeout 86400s;
```
- Result: Persistent wss:// connections through NGINX work reliably.

---

### 4) NGINX could not communicate with the backend container
- Problem: Connection errors when proxying to backend.
- Root cause: `proxy_pass` used `localhost:8000` — inside the nginx container `localhost` is nginx itself.
- Fix: Use Docker Compose service name (Docker DNS):
```nginx
proxy_pass http://backend:8000/ws;
```
- Result: NGINX routes requests to the FastAPI container successfully.

---

### 5) Redis was not persisting chat history
- Problem: Message history lost on reconnect; presence unstable.
- Root cause: State was kept only in process memory.
- Fix: Integrate Redis for persistence:
  - store messages in `chat_history` (list)
  - track online users in `online_users` (set)
  - send recent history to new clients on connect
  - trim history to last 50 messages
- Result: History and presence are durable and consistent.

---

### 6) Docker permission denied on deployment host
- Problem: Docker commands required `sudo`.
- Root cause: Deployment user not in `docker` group.
- Fix:
```bash
sudo usermod -aG docker $USER
newgrp docker
```
- Result: Docker commands run without sudo for the deployment user.

---

### 7) SSH connection dropped after assigning Elastic IP
- Problem: SSH stopped working after Elastic IP assignment.
- Root cause: The instance’s public endpoint changed; local SSH config used old address.
- Fix: Update SSH config / host to use the Elastic IP or DNS name mapped to it.
- Result: SSH connectivity restored.

---

### 8) GitHub Actions deployment failed (timeout)
- Problem: `dial tcp ***:22: i/o timeout` from Actions.
- Root cause: Actions `HOST` secret referenced old IP (not the Elastic IP).
- Fix: Update repository secret with the current Elastic IP.
```
HOST=13.62.142.178
```
- Result: Actions can SSH into the host and deploy.

---

### 9) HTTP-only site (no SSL)
- Problem: Production served only over HTTP.
- Root cause: Certificates not provisioned/configured.
- Fix: Point domain to Elastic IP, obtain Let's Encrypt certs with Certbot, and configure nginx for HTTPS and secure WebSocket proxying.
- Result: App available at `https://whiteobah.space` and wss:// connections succeed.

---

### 10) Terraform provider binary pushed (repo size limit)
- Problem: Pushes rejected — file(s) exceeded GitHub’s 100 MB limit.
- Root cause: `.terraform/` was committed.
- Fix:
```bash
git rm -r --cached terraform/.terraform
```
Add to `.gitignore`:
```
terraform/.terraform/
*.tfstate
*.tfstate.*
```
- Result: Repository pushes succeed; repo is portable.

---

### 11) Reviewer portability: HTTPS config blocked local runs
- Problem: Local reviewers could not start nginx because config referenced server-only certs.
- Root cause: Production NGINX config used by default.
- Fix: Split configuration:
  - `nginx.conf` — HTTP-only (local / reviewer)
  - `nginx-ssl.conf` — HTTPS (production)
  - Add `docker-compose.prod.yml` override to mount `/etc/letsencrypt` only in production
- Result: Reviewers run `docker compose up -d --build` without certificates; production still uses full HTTPS.

---

## Key deployment lessons
- Always use Compose service names for inter-container comms — do not use `localhost`.
- NGINX must explicitly support WebSocket upgrades (HTTP/1.1, Upgrade/Connection headers).
- Keep application state out of process memory for multi-instance or container restarts — Redis is the simplest durable option here.
- Automate endpoint & secret updates (Elastic IP changes, DNS updates) as part of the infra pipeline to avoid manual drift.
- Keep production-only config and secrets out of the default repo configuration; provide local-safe defaults and a clear override path.

## Recommended follow-ups
- Add a lightweight GitHub Actions workflow that lint/builds and validates `docker compose up` in CI (no deploy stage) to catch config regressions early.
- Add a small healthcheck endpoint and Docker Compose `healthcheck` for the backend so orchestrators can detect failure quickly.
- Store deployment host and SSH keys in secrets manager and add a pipeline step that validates SSH reachability before executing the deploy steps.
