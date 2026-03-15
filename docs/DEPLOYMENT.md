# Deployment Guide

## Prerequisites

- Linux VPS with Docker Engine 24+ and Docker Compose v2+
- SSH access to the server
- At least 2 GB RAM and 10 GB disk

## Single-App Deployment

If nepremicnine is the only application on the server:

```bash
# 1. Clone repository
git clone https://github.com/mvelkov9/nepremicnine.git
cd nepremicnine

# 2. Configure environment
cp .env.example .env
nano .env  # Set production values (see below)

# 3. Launch
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# 4. Run database migrations
docker compose exec backend alembic upgrade head

# 5. Verify
curl http://localhost/api/health
```

### Required .env Values

```env
POSTGRES_PASSWORD=<generate strong password>
JWT_SECRET_KEY=<python3 -c "import secrets; print(secrets.token_urlsafe(64))">
APP_ENV=production
CORS_ORIGINS=https://yourdomain.com
```

## Multi-App VPS (Shared Server)

When another app already occupies port 80/443, deploy nepremicnine on a
different port and optionally set up domain-based routing.

### Option 1: Port Separation (Quick)

Edit `docker-compose.prod.yml` to use a different port:

```yaml
services:
  frontend:
    ports:
      - "8080:80"  # instead of "80:80"
  backend:
    ports:
      - "127.0.0.1:8001:8000"  # instead of 8000
```

Access at `http://your-server-ip:8080`.

### Option 2: Domain-Based Routing (Recommended)

Install nginx on the host to route traffic by domain name:

```bash
sudo apt install nginx
```

Create `/etc/nginx/sites-available/nepremicnine`:

```nginx
server {
    listen 80;
    server_name nepremicnine.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/nepremicnine /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# Add SSL with Let's Encrypt
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d nepremicnine.yourdomain.com
```

## Monitoring

```bash
# Check container status
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps

# View logs
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f worker

# Health check
curl http://localhost:8080/api/health
```

## Database Backup

```bash
# Backup
docker compose exec postgres pg_dump -U nepremicnine nepremicnine > backup_$(date +%Y%m%d).sql

# Restore
cat backup_20250101.sql | docker compose exec -T postgres psql -U nepremicnine nepremicnine
```

## Updating

```bash
cd /path/to/nepremicnine
git pull origin main
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose exec backend alembic upgrade head
docker image prune -f
```
