# Deployment Guide

The production frontend is now a Nuxt 4 application served by Nitro on port `3000` inside the container. In the default production compose profile, Docker exposes it as `80:3000`, and browser `/api/*` requests are proxied same-origin through Nitro to the FastAPI backend.

Switching from legacy frontend components to Nuxt UI does **not** require a new host-side service on the VPS. Nuxt UI compiles into the same Nitro frontend bundle you already deploy, so the host requirements stay the same: Docker, the existing reverse proxy, and enough memory for the Node/Nitro container.

As of March 17, 2026, the production deployment path is still a **hybrid** model: GitHub Actions builds and publishes images to GHCR, but the VPS deployment step still pulls the repo and runs `docker compose ... up -d --build` locally. Treat the merged compose invocation below as the current source of truth until Phase 30 simplifies the release path.

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
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T backend alembic upgrade head

# 5. Verify
curl http://localhost/api/health
```

### Required .env Values

```env
POSTGRES_PASSWORD=<generate strong password>
JWT_SECRET_KEY=<python3 -c "import secrets; print(secrets.token_urlsafe(64))">
APP_ENV=production
CORS_ORIGINS=https://yourdomain.com
AUTH_COOKIE_SECURE=true
```

> **Notes:**
>
> - `JWT_SECRET_KEY` must be at least 32 characters in production.
> - Set `AUTH_COOKIE_SECURE=true` for any HTTPS deployment so browser auth cookies are sent only over TLS.
> - `AUTH_COOKIE_SAMESITE=lax` is the current default and is usually appropriate unless your deployment topology requires something stricter or cross-site.

## Multi-App VPS (Shared Server)

When another app already occupies port 80/443, deploy nepremicnine on a
different port and optionally set up domain-based routing.

### Option 1: Port Separation (Quick)

Edit `docker-compose.prod.yml` to use a different port:

```yaml
services:
  frontend:
    ports:
      - "8080:3000" # instead of "80:3000"
  backend:
    ports:
      - "127.0.0.1:8001:8000" # only if 127.0.0.1:8000 is already occupied
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
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f frontend
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f worker

# Health check
curl http://localhost/api/health
```

Always pass both `docker-compose.yml` and `docker-compose.prod.yml`. The production file is an override, not a standalone stack definition.

## Database Backup

```bash
# Backup
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T postgres pg_dump -U nepremicnine nepremicnine > backup_$(date +%Y%m%d).sql

# Restore
cat backup_20250101.sql | docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T postgres psql -U nepremicnine nepremicnine
```

## Updating

```bash
cd /path/to/nepremicnine
git pull origin main
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T backend alembic upgrade head
docker image prune -f
```

This reflects the **current** automation as well: `main` pushes rebuild on the VPS. If you later switch production to pull pinned GHCR images, the VPS will additionally need `docker login ghcr.io` and the compose file should move from `build:` to `image:` references.

## Custom Domain Setup (napoved-nepremicnin.com)

### 1. DNS Configuration

At your domain registrar, create an **A record**:

| Type | Name  | Value           | TTL |
| ---- | ----- | --------------- | --- |
| A    | `@`   | `<your-vps-ip>` | 300 |
| A    | `www` | `<your-vps-ip>` | 300 |

### 2. Host Nginx Config

Create `/etc/nginx/sites-available/napoved-nepremicnin`:

```nginx
server {
    listen 80;
    server_name napoved-nepremicnin.com www.napoved-nepremicnin.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        client_max_body_size 1024M;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/napoved-nepremicnin /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 3. SSL via Let's Encrypt

```bash
sudo certbot --nginx -d napoved-nepremicnin.com -d www.napoved-nepremicnin.com
```

Certbot will auto-configure HTTPS and redirect HTTP → HTTPS.

### 4. Update CORS

In your `.env`:

```env
CORS_ORIGINS=https://napoved-nepremicnin.com,https://www.napoved-nepremicnin.com,http://localhost:3000
AUTH_COOKIE_SECURE=true
```

Restart the backend:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart backend
```

### 5. Verify

```bash
curl -I https://napoved-nepremicnin.com/api/health
```

If uploads still return `413 Request Entity Too Large`, verify the host nginx config and the Docker stack limits. There is no longer a second nginx layer inside the frontend container.

## Runtime Notes

- The backend remains private on `127.0.0.1:8000` by default in production; external traffic should enter through the frontend or your host reverse proxy.
- Because the frontend proxies `/api/*`, the browser can stay same-origin and still use HttpOnly access/refresh cookies for SSR-friendly authentication.
- If you expose the frontend on an alternate host port such as `8080`, update any host nginx `proxy_pass` lines to that port.
- `docker-compose.prod.yml` explicitly clears the dev-only `container-frontend` profile so the production Nitro frontend still starts by default on the VPS.
- Nuxt UI does not add a separate runtime dependency on the VPS; there is no extra nginx layer or client-side asset server to provision beyond the existing frontend container.

## Local Verification

For normal local work, use `corepack pnpm dev` or `corepack pnpm build` from `frontend/`; those scripts already write to isolated local directories such as `.nuxt-dev`, `.nuxt-build`, and `.output-build`.

If you run bare `nuxt` commands on a machine where old generated folders have restrictive ownership, use temporary output folders:

```bash
cd frontend
NUXT_BUILD_DIR=.nuxt-verify NUXT_OUTPUT_DIR=.output-verify npx nuxt build
```
