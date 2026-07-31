# Deployment guide

This repository is structured to support both **local development** and **production deployment**. The application stack is containerized with Docker Compose, fronted by NGINX, and deployed to an AWS EC2 instance.

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

The local configuration serves the application over HTTP and can be started without SSL certificates. The production configuration enables HTTPS using Let’s Encrypt and mounts the certificate directory.

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

## Load balancer architecture

We recommend placing an AWS Application Load Balancer (ALB) in front of the EC2 fleet that runs this Docker Compose stack. Key points:

* TLS termination: terminate TLS at the ALB using AWS Certificate Manager (ACM) when possible. This centralises certificate management and simplifies instance configuration.
* Listeners and forwarding: create listeners on 80 (redirect to 443) and 443. The ALB forwards requests to a Target Group composed of the EC2 instances running the Docker stack.
* WebSocket support: ALB supports WebSocket proxying over HTTP/1.1. Ensure the ALB and target group use HTTP/1.1 and that your NGINX proxy forwards Upgrade and Connection headers so WebSocket upgrades succeed.
* Health checks: configure the target group health check to use a lightweight endpoint (for example `/health` or an NGINX status endpoint). Proper health checks allow the ALB to remove unhealthy instances automatically.
* Security groups: restrict instance security groups to accept traffic from the ALB security group rather than the open internet. The ALB security group should allow inbound 80/443 from the internet.
* Connection draining: enable deregistration delay (connection draining) on the target group so in-flight requests and long-lived WebSocket connections have time to finish when instances are removed.
* Session/state handling: avoid relying on ALB sticky sessions for correctness. Instead, store transient state in Redis (ElastiCache) so any instance can serve any client. If stickiness is required for legacy reasons, enable target group stickiness, but prefer a shared-state architecture.

If you choose to keep Let’s Encrypt/TLS on the instance-level NGINX, you can instead place a Network Load Balancer (NLB) in front of instances to perform TCP passthrough. Terminating TLS at the ALB with ACM is recommended for simplified management and better integration with AWS features.

---

## Auto-scaling approach

Use an Auto Scaling Group (ASG) behind the ALB to provide horizontal scalability and improve availability. Recommended approach:

* Launch configuration / AMI: create a Launch Template that uses a pre-baked AMI or runs user-data to install Docker, Docker Compose, and start the application (for example, `git pull && docker compose up -d --build`). Baking an AMI with Docker preinstalled speeds scale-out significantly.
* Scaling policies:
  - Target tracking: scale based on metrics such as ALBRequestCountPerTarget (requests per instance) or average CPU utilisation. Target tracking simplifies autoscaling by trying to keep the chosen metric near the target value.
  - Step scaling: define step policies for larger spikes to add multiple instances quickly.
  - Configure sensible min/max instance counts and cooldown periods so the group doesn't oscillate.
* WebSocket and connection draining:
  - Set a deregistration delay on the target group (for example 300s) so existing WebSocket connections and in-flight requests are gracefully handled during scale-in.
  - Implement graceful shutdown handlers in containers so the process stops accepting new connections on SIGTERM and finishes processing open connections before exit.
* Stateful vs stateless design:
  - Keep application instances stateless by storing sessions, chat history, and presence data in Redis (ElastiCache) or another central store. This allows any instance to handle any client and simplifies scaling.
  - For rate-limiting, locks, or leader election, use Redis or DynamoDB as shared coordination mechanisms.
* Deployment and rollback:
  - Use rolling updates where new instances are launched and pass health checks before older instances are deregistered.
  - For safer releases, use blue/green deployments (create a new ASG and switch ALB target groups) or leverage AWS CodeDeploy for traffic shifting.
* Observability and tuning:
  - Monitor ALB metrics (RequestCount, TargetResponseTime, HealthyHostCount), EC2 metrics (CPU, memory), and application-level metrics (active WebSocket connections, message queue depth).
  - Use CloudWatch alarms to trigger scale actions and log metrics to a central store for capacity planning.
  - Start with conservative thresholds and iterate based on observed traffic patterns.

---



# Deployment issues encountered and how they were resolved

The application was deployed incrementally on an AWS EC2 instance, and most of the work involved debugging infrastructure, networking, and deployment automation rather than application code. This section records the main issues and their fixes.

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

Persistent WebSocket connections were successfully established through NGINX.

---

## 4. NGINX could not communicate with the backend container

### Problem

NGINX returned connection errors while attempting to proxy requests to the backend.

### Root cause

The proxy configuration used:

```nginx
proxy_pass http://localhost:8000/ws;
```

Inside a container, `localhost` refers to the container itself, not another container. Docker Compose provides internal DNS-based service discovery, so containers must communicate using service names.

### Fix

The proxy target was changed to the backend service name.

```nginx
proxy_pass http://backend:8000/ws;
```

### Result

NGINX successfully routed WebSocket traffic to the FastAPI container.

---

## 5. Redis was not storing chat history

### Problem

Messages disappeared after reconnecting, and online user tracking was inconsistent.

### Root cause

Application state existed only in memory.

### Fix

Redis was integrated as a dedicated persistence layer.

* Messages stored in `chat_history`
* Active users stored in `online_users`
* Chat history sent to new clients on connection
* Message history limited to the most recent 50 entries

### Result

Chat history persisted across reconnects, and online user tracking became reliable.

---

## 6. Docker permission denied

### Problem

Docker commands failed with permission errors.

### Root cause

The deployment user was not a member of the Docker group.

### Fix

The user was added to the Docker group.

```bash
sudo usermod -aG docker $USER
newgrp docker
```

### Result

Docker commands executed without requiring sudo.

---

## 7. SSH connection failed after assigning an Elastic IP

### Problem

After assigning an Elastic IP, the existing SSH connection stopped working.

### Root cause

The Elastic IP changed the instance’s public endpoint, and the SSH client was still attempting to connect to the previous address.

### Fix

The SSH configuration was updated to use the Elastic IP.

### Result

SSH access was restored successfully.

---

## 8. GitHub Actions deployment failed

### Problem

The deployment pipeline failed with:

```text
dial tcp ***:22: i/o timeout
```

### Root cause

The GitHub Actions `HOST` secret still contained the old public IP address instead of the new Elastic IP.

### Fix

The repository secret was updated with the Elastic IP.

```text
HOST=13.62.142.178
```

### Result

GitHub Actions successfully connected to the server and completed automated deployments.

---

## 9. HTTPS configuration for production

### Problem

The application was initially available only over HTTP.

### Root cause

SSL certificates had not been configured.

### Fix

A domain was pointed to the Elastic IP, Let’s Encrypt certificates were generated with Certbot, and NGINX was configured for HTTPS and secure WebSocket proxying.

### Result

The application became available securely at:

```text
https://whiteobah.space
```

with encrypted WebSocket connections over `wss://`.

---

## 10. Terraform provider binary exceeded GitHub’s size limit

### Problem

GitHub rejected the repository push because the Terraform provider binary exceeded the 100 MB file size limit.

### Root cause

The `.terraform/` directory was accidentally committed.

### Fix

The Terraform cache was removed from Git tracking.

```bash
git rm -r --cached terraform/.terraform
```

A `.gitignore` file was added to exclude:

```text
terraform/.terraform/
*.tfstate
*.tfstate.*
```

### Result

The repository became portable, and pushes completed successfully.

---

## 11. Repository portability

### Problem

The HTTPS configuration depended on SSL certificates that existed only on the production server.

### Root cause

The repository contained a production-specific NGINX configuration.

### Fix

The configuration was split into:

* `nginx.conf` (HTTP for local/reviewer deployments)
* `nginx-ssl.conf` (HTTPS for production)

A production Docker Compose override file was added for SSL certificate mounts.

### Result

can run:

```bash
docker compose up -d --build
```

without requiring production certificates, while the production server continues using HTTPS.

## Key deployment

The most significant issues were related to **container networking, reverse proxy configuration, deployment automation, and infrastructure configuration** rather than application code. The final deployment emphasizes stateless application design, automated deployments, and clear separation of local vs production configuration.
