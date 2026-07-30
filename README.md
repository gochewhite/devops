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

  docker compose down
  docker compose up --build -d

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

This version sounds much closer to internal engineering documentation: concise, operational, and focused on reproducibility and maintenance rather than teaching Docker from scratch.
