# 🎬 CinePass — Next-Gen Movie Discovery & Ticket Booking Platform

[![Django](https://img.shields.io/badge/Django-5.1-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Channels](https://img.shields.io/badge/WebSockets-Django_Channels-blue?style=for-the-badge&logo=websocket&logoColor=white)](https://channels.readthedocs.io/)
[![Razorpay](https://img.shields.io/badge/Razorpay-Payment_Gateway-0C2340?style=for-the-badge&logo=razorpay&logoColor=white)](https://razorpay.com/)
[![Celery](https://img.shields.io/badge/Celery-Distributed_Tasks-37814A?style=for-the-badge&logo=celery&logoColor=white)](https://docs.celeryq.dev/)
[![Redis](https://img.shields.io/badge/Redis-Cache_%26_Broker-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io/)
[![ReportLab](https://img.shields.io/badge/ReportLab-PDF_Generation-FF6B6B?style=for-the-badge)](https://www.reportlab.com/)
[![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-7952B3?style=for-the-badge&logo=bootstrap&logoColor=white)](https://getbootstrap.com/)

**CinePass** is a full-featured, enterprise-grade movie discovery and online ticket reservation platform inspired by industry leaders like BookMyShow. Built with **Django 5.x**, **WebSockets (Django Channels)**, **PostgreSQL/SQLite**, **Redis**, **Celery**, **Razorpay Test Mode**, and **ReportLab PDF Engine**, CinePass delivers real-time seat synchronization, atomic row-level concurrency protection, cryptographically signed digital e-tickets with QR codes, automated background email delivery, and an analytics dashboard benchmarked on **100,000+ bookings**.

---

## 📑 Table of Contents

- [✨ Key Features Across 6 Core Pillars](#-key-features-across-6-core-pillars)
  - [1. Movie Discovery & Recommendation](#1-movie-discovery--smart-recommendations)
  - [2. Real-Time Smart Seat Reservation](#2-real-time-smart-seat-reservation)
  - [3. Payment & Booking Management](#3-payment-gateway--booking-management)
  - [4. Automated Ticket Generation & Email](#4-automated-ticket-generation--email-dispatch)
  - [5. Movie Management, Trailers & Verified Reviews](#5-movie-management-trailers--verified-reviews)
  - [6. Admin Analytics & BI Dashboard](#6-admin-analytics--bi-dashboard)
- [🏗️ System Architecture & App Breakdown](#️-system-architecture--app-breakdown)
- [⚙️ Tech Stack](#️-tech-stack)
- [🚀 Quickstart & Local Setup](#-quickstart--local-setup)
- [🔐 Environment Variables Configuration](#-environment-variables-configuration)
- [🧪 Automated Test Suite](#-automated-test-suite)
- [📡 API & Endpoint Directory](#-api--endpoint-directory)
- [📊 Database Schema & Concurrency Design](#-database-schema--concurrency-design)
- [🌐 Production Deployment](#-production-deployment)
- [📄 License & Authors](#-license--authors)

---

## ✨ Key Features Across 6 Core Pillars

### 1. Movie Discovery & Smart Recommendations
* 🔍 **Multi-Parameter Search:** Real-time search across movie titles, descriptions, genres, and cast.
* 🎛️ **Facet Filtering:** Filter shows by City, Cinema/Theater, Genre, Language, Release Date Range, Minimum Rating, and Show Timing (Morning, Afternoon, Evening, Night).
* 📊 **Smart Sorting:** Sort by Popularity, Rating, Newest Release Date, and Ticket Base Price.
* 🤖 **Personalized Recommendation Engine:** Multi-tiered affinity scoring based on user booking history and recently viewed movies.
* 🏷️ **Dynamic Result Count:** Live matching counter and URL query-string-preserving pagination.

### 2. Real-Time Smart Seat Reservation
* 🪑 **Interactive Tiered Seat Layout:** Support for Regular, Premium, VIP, and Recliner seating tiers with dynamic pricing.
* ⚡ **Live WebSocket Seat Sync:** Real-time seat state broadcast (`AVAILABLE`, `RESERVED`, `BOOKED`) via Django Channels (`/ws/shows/<id>/seats/`).
* 🔒 **Atomic Concurrency Protection:** Row-level locking (`select_for_update()`) inside atomic transactions prevents two users from reserving the same seat simultaneously (returns `409 Conflict`).
* ⏳ **2-Minute Reservation Lifecycle:** Automatic countdown timer holds seats for 120 seconds during checkout.
* 🧹 **Automatic Seat Release:** Automatic background expiration via Celery scheduled tasks, lazy access cleanups, and modal dismissal hooks.

### 3. Payment Gateway & Booking Management
* 💳 **Razorpay Integration:** Full server-side order generation and cryptographic HMAC-SHA256 signature verification (`order_id|payment_id`).
* 🛡️ **Double-Booking & Duplicate Guard:** Strict idempotency checks ensure payments cannot be applied twice.
* 🔄 **Seamless Failure & Retry Flow:** On payment cancellation or failure, seats are instantly freed and users can retry with one-click re-ordering.
* 🔔 **Webhook Reconciliation:** Secure HMAC-verified webhook endpoint (`/payments/webhook/`) handling `payment.captured` and `payment.failed` server-to-server events.
* 📜 **Billing Ledger & Payment History:** Dedicated user payment dashboard (`/accounts/payments/`) displaying transaction IDs, gateway references, and status badges.

### 4. Automated Ticket Generation & Email Dispatch
* 🎟️ **High-Resolution PDF Tickets:** Professional PDF generation with custom movie posters, theater info, seat numbers, booking IDs, and barcodes using ReportLab.
* 📱 **Cryptographically Signed QR Code:** HMAC-signed verification token embedded in the PDF for on-site ticket validation (`/bookings/verify/<token>/`).
* 📧 **Background Email Delivery:** Non-blocking asynchronous Celery task with automatic exponential backoff retries on SMTP connection errors.
* 📬 **Live Gmail SMTP Delivery:** Fully tested with Gmail App Password authentication.
* 💾 **1-Click PDF Downloads:** Download previous tickets anytime from Booking History or Payment History.

### 5. Movie Management, Trailers & Verified Reviews
* 🎬 **TMDb Integration & Management:** Import rich movie metadata, posters, backdrops, and cast details directly from TMDb API.
* 📺 **Secure YouTube Trailer Embed:** Video modal popup with responsive sandboxed `<iframe>` embed.
* ⭐ **Verified Purchaser Reviews:** Only users with confirmed past bookings can write reviews and receive the **"Verified Purchaser"** badge.
* 📈 **Dynamic Rating Calculation:** Movie rating and review count recalculate automatically upon review submission/edit.
* 🚩 **Community Moderation:** Built-in review reporting endpoint for inappropriate content.

### 6. Admin Analytics & BI Dashboard
* 📊 **Real-Time Revenue Metrics:** Daily, Weekly, Monthly, and Yearly gross earnings breakdown.
* 🏢 **Theater Occupancy Tracking:** Percentage capacity utilization per theater and screen.
* 🔥 **Leaderboards & Heatmaps:** Top 5 most booked movies, top-performing theaters, and peak booking hours distribution.
* 📉 **Cancellation & Refund Statistics:** Real-time cancellation rate tracking and financial refund ledgers.
* 📥 **CSV Export:** 1-click streaming CSV export of all analytical metrics for custom date ranges.
* 🚀 **100,000+ Record Benchmark:** Sub-50ms query response times using multi-column composite database indexes.

---

## 🏗️ System Architecture & App Breakdown

```
CinePass/
├── apps/
│   ├── core/            # Base abstract models, health check endpoints
│   ├── accounts/        # Custom User model, auth views, profile & payment history
│   ├── movies/          # Movie catalog, TMDb sync commands, search & recommendations
│   ├── theaters/        # City, Theater, Screen, and physical Seat management
│   ├── shows/           # Screening schedules, pricing, seat reservations, WebSockets
│   ├── bookings/        # Booking transactions, PDF ticket generation, QR verification
│   ├── payments/        # Razorpay integration, signature verify, webhooks, retry APIs
│   ├── reviews/         # Verified viewer ratings, reviews, editing, moderation reports
│   ├── dashboard/       # Admin analytics BI dashboard, ORM aggregations, CSV exports
│   └── recommendations/ # Content-based & collaborative recommendation pipelines
├── movie_discovery_system/
│   ├── settings/        # base.py, dev.py, prod.py settings modules
│   ├── asgi.py          # ASGI application routing HTTP & WebSockets (Daphne)
│   ├── wsgi.py          # WSGI application entrypoint (Gunicorn)
│   ├── celery.py        # Celery task app configuration
│   └── urls.py          # Master URL router
├── static/              # CSS, JavaScript, images, and fallback assets
├── templates/           # Clean Bootstrap 5 templates & reusable components
├── manage.py            # Django CLI management entrypoint
└── requirements.txt     # Python dependency specifications
```

---

## ⚙️ Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend Framework** | Django 5.1, Python 3.12+ |
| **Real-Time / Async** | Django Channels 4.x, Daphne ASGI, WebSockets |
| **Task Queue & Cache** | Celery 5.x, Redis 7.x |
| **Payment Gateway** | Razorpay SDK (Test & Production Modes) |
| **Document Generation** | ReportLab (PDF), QRCodegen, Cryptographic Signers |
| **Frontend UI** | HTML5, CSS3, Bootstrap 5.3, FontAwesome 6, Chart.js |
| **Database** | SQLite (Dev) / PostgreSQL (Production) with Multi-column Indexes |
| **Deployment** | Render (Web & Celery Services), Vercel, Whitenoise |

---

## 🚀 Quickstart & Local Setup

### 1. Clone the Repository
```bash
git clone https://github.com/ynaveensai1368-source/CinePass.git
cd CinePass
```

### 2. Create and Activate Virtual Environment
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
*(Fill in your TMDb API Key, Razorpay Keys, and Gmail App Password)*

### 5. Run Database Migrations
```bash
python manage.py migrate
```

### 6. Seed Demo Catalog Data
```bash
python manage.py seed_demo_data
```

### 7. Start the ASGI Development Server
```bash
python manage.py runserver
```
Visit **`http://127.0.0.1:8000`** in your browser!

---

## 🔐 Environment Variables Configuration

Create a `.env` file in the root directory:

```env
# Django Core Settings
SECRET_KEY=your-super-secret-django-key
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost,testserver

# TMDb API Integration
TMDB_API_KEY=your_tmdb_api_key
TMDB_ACCESS_TOKEN=your_tmdb_access_token

# Razorpay Payment Gateway
RAZORPAY_KEY_ID=rzp_test_your_key_id
RAZORPAY_KEY_SECRET=your_razorpay_secret_key
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret

# Celery & Redis
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Gmail SMTP Email Delivery
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_16_char_google_app_password
DEFAULT_FROM_EMAIL=CinePass <your_email@gmail.com>

# CORS & CSRF
FRONTEND_URL=http://localhost:3000
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:8000
CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
```

---

## 🧪 Automated Test Suite

CinePass features a comprehensive test suite covering discovery, booking transactions, concurrency locks, payment signatures, webhooks, analytics permissions, and seat releases.

Run all tests across all apps:
```bash
python manage.py test movies shows reviews bookings payments dashboard accounts
```

```
Found 27 test(s).
System check identified no issues (0 silenced).
----------------------------------------------------------------------
Ran 27 tests in 13.900s

OK
```

---

## 📡 API & Endpoint Directory

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/` | Home page with curated carousels | No |
| `GET` | `/explore/` | Movie Discovery & Multi-Filter Catalog | No |
| `GET` | `/movie/<slug>/` | Movie Details, Trailer Modal, Verified Reviews | No |
| `GET` | `/shows/<id>/seats/` | Real-time Interactive Seat Map UI | No |
| `GET` | `/shows/api/<id>/seats/` | REST API for Show Seat Availability | No |
| `POST` | `/shows/api/<id>/seats/reserve/` | Atomic 2-Minute Seat Reservation Endpoint | Yes |
| `DELETE`| `/shows/api/<id>/seats/reserve/` | Release Held Seat Reservation | Yes |
| `GET` | `/payments/checkout/<show_id>/` | Payment Checkout Summary & Gateway Order | Yes |
| `POST` | `/payments/verify/` | Server-Side HMAC Payment Verification | Yes |
| `POST` | `/payments/api/failed/` | Payment Failure Handler & Instant Seat Release | Yes |
| `POST` | `/payments/api/retry/` | Refresh Expired Order / Payment Retry | Yes |
| `POST` | `/payments/webhook/` | Razorpay S2S Webhook Listener | No (HMAC Verified) |
| `GET` | `/accounts/bookings/` | User Booking History | Yes |
| `GET` | `/accounts/payments/` | User Payment Transactions & Invoices | Yes |
| `GET` | `/bookings/download/<id>/` | Download Official PDF Ticket | Yes |
| `GET` | `/bookings/verify/<token>/` | Cryptographic QR Scanner Verification | No |
| `GET` | `/dashboard/` | Admin Analytics BI Dashboard | Admin / Staff |
| `GET` | `/dashboard/export/csv/` | Export Analytics Metrics to CSV | Admin / Staff |

---

## 📊 Database Schema & Concurrency Design

```
+----------------+       +------------------+       +-------------------+
|     Movie      |1-----*|       Show       |*-----1|      Screen       |
+----------------+       +------------------+       +-------------------+
                                  |                           |
                                  | 1                         | 1
                                  |                           |
                                  *                           *
                         +------------------+       +-------------------+
                         |     ShowSeat     |*-----1|       Seat        |
                         +------------------+       +-------------------+
                                  |
                                  | *
                         +------------------+       +-------------------+
                         | SeatReservation  |*-----1|       User        |
                         +------------------+       +-------------------+
                                  |                           |
                                  | 1                         | 1
                                  |                           |
                         +------------------+                 |
                         |     Booking      |*----------------+
                         +------------------+
                                  |
                                  | 1
                         +------------------+
                         |     Payment      |
                         +------------------+
```

### Concurrency Guarantees
- `select_for_update()` ensures exclusive row-level locks on `ShowSeat` during checkout.
- Database uniqueness constraints prevent concurrent creation of overlapping reservations.
- Cryptographic TimestampSigners guarantee tickets cannot be forged or tampered with.

---

## 🌐 Production Deployment

For detailed deployment blueprints on Render and PostgreSQL, refer to **[`DEPLOYMENT.md`](./DEPLOYMENT.md)**.

```bash
# Build script execution on Render
chmod +x build.sh
./build.sh
```

---

## 📄 License & Authors

This project is developed and maintained for the **CinePass** ticket booking system.
Distributed under the **MIT License**. See `LICENSE` for more information.

*Built with ❤️ using Django 5, WebSockets, and Razorpay.*