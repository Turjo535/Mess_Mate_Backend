# Mess Mate Backend API

A Django REST Framework backend for **Mess Mate** — a shared housing / mess management system covering user authentication, mess membership & invitations, daily meal tracking, financial cycle accounting, and in-app notifications.

---

## Tech Stack

- **Framework:** Django 6.0.6, Django REST Framework
- **Database:** PostgreSQL 16
- **Async Tasks & Broker:** Celery, Celery Beat, Redis 7, `django-celery-results`
- **Authentication:** JWT (`djangorestframework-simplejwt`) + Google Sign-In (`firebase-admin`)
- **API Docs:** OpenAPI 3 / Swagger / ReDoc (`drf-spectacular`)
- **Containerization:** Docker & Docker Compose

---

## Project Structure

```text
Mess_Mate_Project/
├── Mess_Mate_Project/       # Project settings, root URLs, Celery config
├── User_Authentication/     # Registration, JWT Sign-In, Google Auth, OTP, Profile
├── Mess_Management/         # Mess creation, Invitations, Manager switch, Leave, Notifications
├── Meal_Tracking/           # Meal schedules, Breaks, Mess-wide Meal-Off, Meal reports
├── Financial_Management/    # Mess cycles, Member deposits, Bazar, Utilities, Financial summary
├── docker-compose.yml       # Services: redis, db, web, celery, beat
├── Dockerfile
└── requirements.txt
```

---

## Getting Started (How to Run)

### 1. Prerequisites
- Docker & Docker Compose installed
- A Firebase Admin SDK service-account JSON file (for Google Auth)
- A Gmail/SMTP app password (for OTP and invitation emails)

### 2. Environment Variables (`.env`)
Create a `.env` file in the project root with the following variables:

```env
Django_Secret_Key=your-django-secret-key

# PostgreSQL
DB_NAME=Mess_Mate
DB_USER=postgres
DB_PASSWORD=Mess_Mate
DB_HOST=db
DB_PORT=5432

# Redis / Celery
CELERY_BROKER_URL=redis://redis:6379/0

# Firebase Admin SDK JSON path
FIREBASE_ACCOUNT_KEY=messmate-firebase-adminsdk.json

# SMTP Email (Gmail)
EMAIL_USER=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
EMAIL_FROM=your-email@gmail.com

# Frontend URL (for email links)
FRONTEND_URL=http://localhost:5173

# Linux user mapping for Docker volumes
HOST_UID=1000
HOST_GID=1000
```

### 3. Start All Services with Docker Compose

```bash
export HOST_UID=$(id -u) HOST_GID=$(id -g)
docker compose up --build -d
```

This starts 5 containers:
- `mess_mate_db` — PostgreSQL 16 (exposed on host port `5433`)
- `mess_mate_redis` — Redis 7
- `mess_mate_web` — Django API server on `http://localhost:8000` (auto-runs `migrate`)
- `mess_mate_celery` — Celery background worker (invitation emails, async tasks)
- `mess_mate_beat` — Celery Beat scheduler

### 4. Useful Docker Commands

```bash
# View logs
docker compose logs -f web celery

# Create an admin superuser
docker exec -it mess_mate_web python manage.py createsuperuser

# Run migrations manually
docker exec mess_mate_web python manage.py migrate

# Run unit tests
docker exec mess_mate_web python manage.py test
docker exec mess_mate_web python manage.py test Financial_Management -v 2
docker exec mess_mate_web python manage.py test Mess_Management -v 2
```

---

## Interactive API Documentation

Once the server is running:

- **Swagger UI:** `http://localhost:8000/api/schema/swagger/`
- **ReDoc:** `http://localhost:8000/api/schema/redoc/`
- **OpenAPI Schema (for Postman import):** `http://localhost:8000/api/schema/`
- **Django Admin:** `http://localhost:8000/admin/`

> **Postman Tip:** In Postman, click **Import → Link** and paste `http://localhost:8000/api/schema/` to import all endpoints automatically.

---

## Authentication

All protected endpoints use **JWT Bearer Authentication**:

```http
Authorization: Bearer <access_token>
```

- Access token lifetime: **7 days**
- Refresh token lifetime: **10 days**

---

## API Endpoints Reference

### 1. User Authentication (`/api/auth/`)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/api/auth/google-auth/` | Public | Verify Firebase `id_token`, create/update user, return JWT tokens |
| `POST` | `/api/auth/register/` | Public | Register user (`multipart/form-data`), sends 6-digit verification OTP email |
| `POST` | `/api/auth/signin/` | Public | Sign in with `email` & `password`, returns `access` and `refresh` JWTs |
| `GET` | `/api/auth/user/` | Bearer | Get authenticated user profile & profile-completion flag (`chk`) |
| `PATCH` | `/api/auth/user/update-profile/` | Bearer | Update profile fields (`name`, `phone`, `date_of_birth`, `permanent_address`, `profession`, `institution`, `profile_picture`) |
| `POST` | `/api/auth/send-otp/` | Public | Send/resend 6-digit OTP to `email` |
| `POST` | `/api/auth/verify-otp/` | Public | Verify `email` + `otp` (15-min expiry) and activate account |
| `POST` | `/api/auth/forgot-password/` | Public | Reset password using `email`, `otp`, `new_password`, `confirm_password` |
| `POST` | `/api/auth/change-password/` | Bearer | Change password with `current_password`, `new_password`, `confirm_password` |

---

### 2. Mess Management (`/api/mess/`)

| Method | Endpoint | Auth / Role | Description |
|---|---|---|---|
| `POST` | `/api/mess/create-mess/` | Verified User | Create a new mess (`name`, `mess_address`, `instruction`, `capacity`, `contact_number`). Creator becomes manager. |
| `GET` | `/api/mess/<mess_id>/invitations/` | Mess Manager | List pending invitations for the mess |
| `POST` | `/api/mess/<mess_id>/invitations/` | Mess Manager | Bulk invite up to 20 emails (`{"emails": [...]}`). Notifies registered users in-app and emails unregistered users via Celery. |
| `DELETE` | `/api/mess/<mess_id>/invitations/<pk>/` | Mess Manager | Cancel a pending invitation |
| `GET` | `/api/mess/invitations/` | Verified User | List pending invitations addressed to the current user |
| `GET` | `/api/mess/invitations/lookup/?token=...` | Public | Validate an email invitation token (used during registration) |
| `PATCH` | `/api/mess/invitations/<pk>/` | Verified User | Accept or decline an invitation (`{"status": "accepted" \| "declined"}`). Accepting adds user to mess and notifies all members (`member_joined`). |
| `POST` | `/api/mess/<mess_id>/switch-manager/` | Mess Manager | Transfer manager role to another member (`{"new_manager_id": <user_id>}`) |
| `POST` | `/api/mess/<mess_id>/leave/` | Mess Member | Leave the mess. Sole manager cannot leave while other members remain. Notifies remaining members (`member_left`). |
| `GET` | `/api/mess/notifications/` | Bearer | List user's latest 50 notifications + `unread_count` |
| `PATCH` | `/api/mess/notifications/<pk>/` | Bearer | Mark notification read/unread (`{"is_read": true}`) |

---

### 3. Meal Tracking (`/api/meal/`)

#### Meal Schedules (e.g., Breakfast, Lunch, Dinner)
| Method | Endpoint | Auth / Role | Description |
|---|---|---|---|
| `GET` | `/api/meal/<mess_id>/schedules/` | Mess Member | List daily meal schedules for the mess |
| `POST` | `/api/meal/<mess_id>/schedules/` | Mess Manager | Create a meal schedule (`meal_type`, `meal_time`, `meal_select_time`) |
| `GET` | `/api/meal/<mess_id>/schedules/<pk>/` | Mess Member | Get a single meal schedule |
| `PATCH` | `/api/meal/<mess_id>/schedules/<pk>/` | Mess Manager | Partially update a meal schedule |
| `DELETE` | `/api/meal/<mess_id>/schedules/<pk>/` | Mess Manager | Delete a meal schedule (blocked if referenced by breaks/meal-offs) |

#### Daily Meal Status & Member Breaks
| Method | Endpoint | Auth / Role | Description |
|---|---|---|---|
| `GET` | `/api/meal/<mess_id>/meals/?date=YYYY-MM-DD` | Mess Member | Get meal status for a date (defaults to today): your `eating` flag, `total_eating` headcount, and `meal_off` status per slot |
| `GET` | `/api/meal/<mess_id>/breaks/` | Mess Member | List your active/upcoming meal breaks |
| `POST` | `/api/meal/<mess_id>/breaks/` | Mess Member | Create a personal meal break (`start_date`, `start_meal`, `end_date`, `end_meal`, `reason`). Rejects `409` on overlap. Notifies manager (`meal_break_added`). |
| `DELETE` | `/api/meal/<mess_id>/breaks/<pk>/` | Mess Member | Cancel a future break (only before `start_date`) |
| `POST` | `/api/meal/<mess_id>/breaks/resume/` | Mess Member | Carve/resume meals from an active break (`from_date`, `from_meal`, `to_date`, `to_meal`). Notifies manager (`meal_break_resumed`). |

#### Mess-Wide Meal-Off (Manager)
| Method | Endpoint | Auth / Role | Description |
|---|---|---|---|
| `GET` | `/api/meal/<mess_id>/meal-off/` | Mess Member | List active/upcoming mess-wide meal-offs |
| `POST` | `/api/meal/<mess_id>/meal-off/` | Mess Manager | Turn off meals for the whole mess (`start_date`, `start_meal`, `end_date`, `end_meal`, `reason`). Notifies all members (`meal_off`). |
| `DELETE` | `/api/meal/<mess_id>/meal-off/<pk>/` | Mess Manager | Cancel a future meal-off. Notifies all members (`meal_off_cancelled`). |
| `POST` | `/api/meal/<mess_id>/meal-off/resume/` | Mess Manager | Carve/resume specific meals from a meal-off. Notifies all members (`meal_off_cancelled`). |

#### Reports & Past Meal Adjustments
| Method | Endpoint | Auth / Role | Description |
|---|---|---|---|
| `GET` | `/api/meal/<mess_id>/members/` | Mess Member | List brief info (`id`, `name`, `is_manager`) of all mess members |
| `GET` | `/api/meal/<mess_id>/members/<member_id>/meals/?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` | Self or Manager | Detailed meal report (max 93 days): per-day breakdown, eaten/not-eaten totals, and breakdown by reason (`meal_off`, `not_joined`, `break`) |
| `POST` | `/api/meal/<mess_id>/members/<member_id>/meals/off/` | Mess Manager | Mark past meals off for a member (up to 93 days back). Notifies member (`meal_marked_off`). |
| `POST` | `/api/meal/<mess_id>/members/<member_id>/meals/restore/` | Mess Manager | Restore past meals for a member. Notifies member (`meal_restored`). |

---

### 4. Financial Management (`/api/financial/`)

#### Mess Cycles
| Method | Endpoint | Auth / Role | Description |
|---|---|---|---|
| `GET` | `/api/financial/<mess_id>/mess-cycle/` | Mess Manager | List all cycles (supports `?cycle_id=<id>` or `?latest=true`) |
| `POST` | `/api/financial/<mess_id>/mess-cycle/` | Mess Manager | Create a billing cycle (`name`, `start_date`, `end_date`). Validates against overlapping cycles. Notifies all members (`cycle_created`). |
| `PATCH` | `/api/financial/<mess_id>/mess-cycle/<pk>/` | Mess Manager | Partially update a cycle (with overlap validation). Notifies all members (`cycle_updated`). |

#### Member Deposits
| Method | Endpoint | Auth / Role | Description |
|---|---|---|---|
| `GET` | `/api/financial/<mess_id>/member-deposit/` | Mess Manager | List deposits for the mess |
| `POST` | `/api/financial/<mess_id>/member-deposit/` | Mess Manager | Add deposit (`member`, `amount`, `section`: `"Bazar"` or `"Utilities"`). Notifies all members (`deposit_added`). |
| `PATCH` | `/api/financial/<mess_id>/member-deposit/<pk>/` | Mess Manager | Update a deposit. Notifies all members (`deposit_updated`). |
| `DELETE` | `/api/financial/<mess_id>/member-deposit/<pk>/` | Mess Manager | Delete a deposit. Notifies all members (`deposit_deleted`). |

#### Mess Bazar (Grocery Expenses)
| Method | Endpoint | Auth / Role | Description |
|---|---|---|---|
| `GET` | `/api/financial/<mess_id>/mess-bazar/` | Mess Member | List all bazar entries |
| `POST` | `/api/financial/<mess_id>/mess-bazar/` | Mess Member | Add bazar item (`multipart/form-data`: `member`, `product_name`, `product_quantity`, `product_price`, `product_image`). Notifies all members (`bazar_added`). |
| `PATCH` | `/api/financial/<mess_id>/mess-bazar/<pk>/` | Manager or Creator | Update a bazar item. Notifies all members (`bazar_updated`). |
| `DELETE` | `/api/financial/<mess_id>/mess-bazar/<pk>/` | Manager or Creator | Delete a bazar item. Notifies all members (`bazar_deleted`). |

#### Mess Utilities
| Method | Endpoint | Auth / Role | Description |
|---|---|---|---|
| `GET` | `/api/financial/<mess_id>/mess-utilities/` | Mess Member | List all utility expenses |
| `POST` | `/api/financial/<mess_id>/mess-utilities/` | Mess Member | Add utility expense (`utility_name`, `description`, `utility_cost`). Notifies all members (`utility_added`). |
| `PATCH` | `/api/financial/<mess_id>/mess-utilities/<pk>/` | Mess Manager | Update a utility expense. Notifies all members (`utility_updated`). |
| `DELETE` | `/api/financial/<mess_id>/mess-utilities/<pk>/` | Mess Manager | Delete a utility expense. Notifies all members (`utility_deleted`). |

#### Cycle Financial & Meal Summary
| Method | Endpoint | Auth / Role | Description |
|---|---|---|---|
| `GET` | `/api/financial/<mess_id>/financial-summary/<cycle_id>/` | Mess Member | Returns cycle totals (`total_bazar_deposits`, `total_utilities_deposits`, `total_deposits`, `total_bazar`, `total_utilities`, `bazar_balance`, `utilities_balance`, `overall_balance`, `total_meals_eaten`, `per_meal_cost`) along with `meal_summary` (per-member eaten/off/break/not_joined counts up to today). |

---

## Notification Types Overview

All notifications are stored in `Mess_Management.Notification` and retrieved via `GET /api/mess/notifications/`. Actors are excluded from receiving notifications for their own actions.

| Module | Notification `type` values |
|---|---|
| **Mess Management** | `mess_invitation`, `invitation_accepted`, `invitation_declined`, `invitation_expired`, `member_joined`, `member_left` |
| **Meal Tracking** | `meal_break_added`, `meal_break_resumed`, `meal_off`, `meal_off_cancelled`, `meal_marked_off`, `meal_restored` |
| **Financial Management** | `cycle_created`, `cycle_updated`, `deposit_added`, `deposit_updated`, `deposit_deleted`, `bazar_added`, `bazar_updated`, `bazar_deleted`, `utility_added`, `utility_updated`, `utility_deleted` |
