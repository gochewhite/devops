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

## Deployment issues encountered and how they were resolved

The application was deployed incrementally on an AWS EC2 instance. Most of the work involved debugging infrastructure, networking, and deployment automation rather than application code. Below are the major issues encountered and the concrete fixes applied during the production rollout.

### 1. Docker Compose configuration failure

Problem

The application failed to start with the error:

```
services.build must be a mapping
```

Root cause

The `docker-compose.yml` file had incorrect YAML indentation: the `build` directive was placed at the wrong level so Docker Compose could not parse the service definition.

Fix

Restructure the Compose file with the correct indentation:

```yaml
services:
  backend:
    build: .
```

Result

Docker Compose successfully built the backend image and started all containers.

---

### 2. NGINX served the default page instead of the application

Problem

Accessing the server displayed NGINX's default welcome page rather than the chat application.

Root cause

The `frontend` directory was not mounted into the NGINX container.

Fix

Mount the frontend as a read-only volume:

```yaml
volumes:
  - ./frontend:/usr/share/nginx/html:ro
```

Result

NGINX began serving the application frontend correctly.

---

### 3. WebSocket connections failed through NGINX

Problem

The frontend loaded, but real-time messaging failed; clients continuously reported `Disconnected`.

Root cause

NGINX was proxying WebSocket requests as regular HTTP and was not forwarding the required upgrade headers.

Fix

Update the reverse proxy configuration to support WebSocket upgrade and increase timeouts:

```nginx
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
proxy_read_timeout 86400s;
```

Result

Persistent WebSocket connections were successfully established through NGINX.

---

### 4. NGINX could not communicate with the backend container

Problem

NGINX returned connection errors while attempting to proxy requests to the backend.

Root cause

The proxy used `localhost:8000`; inside the NGINX container, `localhost` refers to the container itself. Containers must communicate using Compose service names via Docker DNS.

Fix

Point the proxy to the service name:

```nginx
proxy_pass http://backend:8000/ws;
```

Result

NGINX successfully routed WebSocket traffic to the FastAPI container.

---

### 5. Redis was not storing chat history

Problem

Messages disappeared after reconnecting, and online user tracking was inconsistent.

Root cause

Application state was kept only in memory.

Fix

Integrate Redis as a persistence layer:

* Store messages in `chat_history`.
* Track online users in `online_users`.
* Send recent chat history to new clients on connect.
* Trim history to the most recent 50 messages.

Result

Chat history persisted across reconnects and presence tracking stabilized.

---

### 6. Docker permission denied

Problem

Docker commands failed with permission errors for the deployment user.

Root cause

The deployment user was not in the `docker` group.

Fix

Add the user to the docker group and refresh group membership:

```bash
sudo usermod -aG docker $USER
newgrp docker
```

Result

Docker commands executed without `sudo`.

---

### 7. SSH connection failed after assigning an Elastic IP

Problem

Existing SSH sessions dropped after assigning an Elastic IP.

Root cause

The instance's public endpoint changed; clients were still connecting to the previous address.

Fix

Update SSH client configuration to use the Elastic IP (or the DNS name mapped to it).

Result

SSH connectivity was restored and stable.

---

### 8. GitHub Actions deployment failed

Problem

The deployment pipeline failed with a network timeout when attempting to SSH:

```
dial tcp ***:22: i/o timeout
```

Root cause

The Actions `HOST` secret contained the old IP address rather than the Elastic IP.

Fix

Update the repository secret with the Elastic IP:

```text
HOST=13.62.142.178
```

Result

GitHub Actions connected to the server and completed the deployment successfully.

---

### 9. HTTPS configuration for production

Problem

The application was initially available only over HTTP.

Root cause

SSL certificates were not configured on the server.

Fix

Point a domain to the Elastic IP, generate certificates with Certbot, and configure NGINX for HTTPS and secure WebSocket proxying.

Result

The application served securely at `https://whiteobah.space` and WebSocket connections used `wss://`.

---

### 10. Terraform provider binary exceeded GitHub's size limit

Problem

Pushes were rejected because the Terraform provider binary in `.terraform/` exceeded GitHub's 100 MB limit.

Root cause

The `.terraform/` cache directory was committed to the repository accidentally.

Fix

Remove the cache from git tracking and add appropriate ignores:

```bash
git rm -r --cached terraform/.terraform
```

Add to `.gitignore`:

```
terraform/.terraform/
*.tfstate
*.tfstate.*
```

Result

Repository pushes succeeded and the repo became portable.

---

### 11. Repository portability for reviewers

Problem

The HTTPS configuration depended on production-only SSL certificates, preventing reviewers from running the app locally.

Root cause

Production-specific NGINX configuration was kept in the default configuration file.

Fix

Split configuration into:

* `nginx.conf` — HTTP configuration for local reviewers
* `nginx-ssl.conf` — HTTPS configuration for production

Provide a `docker-compose.prod.yml` override that mounts `/etc/letsencrypt` into the nginx container only in production.

Result

Reviewers can run `docker compose up -d --build` locally without certificates, while the production server uses full HTTPS.

---

## Key deployment lessons

The primary failures were related to container networking, reverse proxy configuration, deployment automation, and infrastructure configuration rather than application logic. Final state:

* Docker service discovery (use service names, not `localhost`) is essential for inter-container communication.
* NGINX must be configured to properly upgrade and proxy WebSocket connections.
* Redis provides durable, shared application state for history and presence.
* GitHub Actions and Terraform provide reproducible, automated deployment and infrastructure provisioning.

These lessons are captured in the repository and the operational runbook above to help future reviewers and operators reproduce and maintain the environment.
