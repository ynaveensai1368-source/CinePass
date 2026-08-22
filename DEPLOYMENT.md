# CinePass Production Deployment Guide

This guide provides step-by-step instructions for deploying the **CinePass** platform to production across **Render**, **Upstash Redis**, and **Vercel**.

---

## 1. Environment Variables Reference

Ensure all environment variables are securely configured in your deployment dashboards (never commit secrets to version control).

| Environment Variable | Description / Sample Value | Service |
| :--- | :--- | :--- |
| `DJANGO_SECRET_KEY` | Long random cryptographic key | Render Web & Worker |
| `DJANGO_DEBUG` | Set to `False` in production | Render Web & Worker |
| `ALLOWED_HOSTS` | `cinepass-api.onrender.com,yourdomain.com` | Render Web |
| `CORS_ALLOWED_ORIGINS` | `https://cinepass.vercel.app,https://yourdomain.com` | Render Web |
| `CSRF_TRUSTED_ORIGINS` | `https://cinepass-api.onrender.com,https://cinepass.vercel.app` | Render Web |
| `DATABASE_URL` | PostgreSQL URI: `postgres://user:pass@ep-xyz.region.postgres.render.com/dbname` | Render Web & Worker |
| `REDIS_URL` | Upstash Redis URI: `rediss://default:pass@region.upstash.io:6379` | Render Web & Worker |
| `CELERY_BROKER_URL` | Upstash Redis URI: `rediss://default:pass@region.upstash.io:6379/0` | Render Web & Worker |
| `CELERY_RESULT_BACKEND` | Upstash Redis URI: `rediss://default:pass@region.upstash.io:6379/0` | Render Web & Worker |
| `RESEND_API_KEY` | Resend API Key: `re_...` | Render Web & Worker |
| `RESEND_FROM_EMAIL` | Sender address: `CinePass <onboarding@resend.dev>` or verified domain | Render Web & Worker |
| `RAZORPAY_KEY_ID` | Production Razorpay Key ID: `rzp_live_...` | Render Web & Vercel |
| `RAZORPAY_KEY_SECRET` | Production Razorpay Secret: `live_secret_...` | Render Web |
| `RAZORPAY_WEBHOOK_SECRET` | Production Razorpay Webhook Secret: `whsec_...` | Render Web |
| `TMDB_API_KEY` | TMDb v3 API Key | Render Web |
| `NEXT_PUBLIC_WS_URL` | `wss://cinepass-api.onrender.com` | Vercel Frontend |

---

## 2. Setting Up Upstash Redis

1. Sign in to [Upstash Console](https://console.upstash.com/).
2. Click **Create Database** -> Name: `cinepass-redis`, Cloud: AWS, Region: Nearest.
3. Select **TLS Enabled** (secure connection).
4. Copy the `rediss://` endpoint URI and set it as `REDIS_URL`, `CELERY_BROKER_URL`, and `CELERY_RESULT_BACKEND`.

---

## 3. Deploying Django Backend to Render

### A. Create PostgreSQL Database
1. Go to [Render Dashboard](https://dashboard.render.com/) -> Click **New +** -> **PostgreSQL**.
2. Name: `cinepass-db`, Region: Oregon (or nearest).
3. Copy the **Internal Database URL** or **External Database URL** and set as `DATABASE_URL`.

### B. Create Web Service (ASGI / Daphne)
1. Click **New +** -> **Web Service**.
2. Connect your Git repository (`Book_by_show-main`).
3. **Environment**: Python 3.11+.
4. **Build Command**:
   ```bash
   pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate
   ```
5. **Start Command** (Daphne ASGI Server for WebSockets):
   ```bash
   daphne -b 0.0.0.0 -p $PORT movie_discovery_system.asgi:application
   ```
6. Add all required Environment Variables listed in Section 1.

### C. Create Background Worker (Celery)
1. Click **New +** -> **Background Worker**.
2. Connect the same repository.
3. **Build Command**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Start Command**:
   ```bash
   celery -A movie_discovery_system worker --loglevel=info
   ```
5. Attach the required Environment Variables (`DATABASE_URL`, `REDIS_URL`, `CELERY_BROKER_URL`, `RESEND_API_KEY`, `RESEND_FROM_EMAIL`).

---

## 4. Deploying Frontend to Vercel

1. Log in to [Vercel Dashboard](https://vercel.com/) -> Click **Add New Project**.
2. Import repository.
3. Set **Framework Preset**: Next.js / Create React App.
4. Environment Variables:
   - `NEXT_PUBLIC_API_BASE_URL`: `https://cinepass-api.onrender.com`
   - `NEXT_PUBLIC_WS_URL`: `wss://cinepass-api.onrender.com`
   - `NEXT_PUBLIC_RAZORPAY_KEY_ID`: `rzp_live_...`
5. Click **Deploy**.

---

## 5. Verification Checklist

- [ ] PostgreSQL database migrations applied cleanly.
- [ ] ASGI WebSocket endpoint `/ws/shows/<show_id>/seats/` accepts connections.
- [ ] Celery worker task `expire_seat_reservations()` cleans up 2-minute holds.
- [ ] Razorpay production webhook endpoint `/api/payments/verify/` returns HTTP 200 OK.
- [ ] PDF e-ticket generation and SMTP email dispatch functioning.
