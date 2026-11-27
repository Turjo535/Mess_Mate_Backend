# AI Agent Guidelines — Mess Mate Backend

This document defines the architecture, coding conventions, and operational rules for AI agents working on the **Mess Mate** Django REST Framework backend.

---

## 1. Environment & Execution Rules

- **Django runs inside Docker** (`mess_mate_web` container). Do **not** assume host Python has Django or project dependencies installed.
- **Syntax checks** on the host:
  ```bash
  python3 -m py_compile <file.py>
  ```
- **Running Django commands & tests** (inside Docker):
  ```bash
  docker exec mess_mate_web python manage.py test
  docker exec mess_mate_web python manage.py migrate
  docker exec mess_mate_web python manage.py check
  ```
- **Celery & Redis** run in `mess_mate_celery`, `mess_mate_beat`, and `mess_mate_redis`. Use `CELERY_BROKER_URL` from environment variables (never hardcode `localhost`).

---

## 2. Codebase Architecture

| App | Responsibility | Key Models |
|---|---|---|
| `User_Authentication` | JWT Auth, Google Sign-In (Firebase), Registration, OTP, Profile | `UserModel`, `OTPModel` |
| `Mess_Management` | Mess creation, Invitations, Manager switch, Leave, Notifications | `Mess`, `Mess_Members`, `MessInvitation`, `Notification` |
| `Meal_Tracking` | Daily meal schedules, Personal breaks, Mess-wide meal-offs, Reports | `MealSchedule`, `MealBreak`, `MealOff` |
| `Financial_Management` | Billing cycles, Member deposits, Bazar, Utilities, Cycle summaries | `MessCycle`, `MemberDeposit`, `MessBazar`, `MessUtilities` |

---

## 3. Coding Conventions

### Views & Routing
- Use `APIView` (or DRF generics where appropriate) with explicit `@extend_schema(tags=[TAG], ...)` decorators for `drf-spectacular`.
- Scope mess-level endpoints under `<int:mess_id>/...` in each app's `urls.py`.
- Use **separate dedicated `APIView` classes** for `PATCH`/`DELETE` item operations (`UpdateMessCycleView`, `UpdateMemberDepositView`, `UpdateMessBazarView`, `UpdateMessUtilitiesView`) rather than mixing collection and detail routes into one view.

### Permissions
- Always pair `IsAuthenticated` with mess-scoped permissions from `Mess_Management.permissions`:
  - `IsVerifiedUser` — checks `user.is_active`
  - `IsMessMember` — verifies user belongs to `mess_id`
  - `IsMessManager` — verifies user is a manager (`is_manager=True`) for `mess_id`
- For `MessBazar` updates/deletes, allow either a mess manager **or** the member who created the item.

### Business Logic & Services
- Keep ORM aggregations, date-range calculations, and notification dispatch in each app's `services.py` — avoid putting heavy business logic directly in views.
- Use lazy imports inside `services.py` when importing across apps (e.g., `Financial_Management` importing from `Meal_Tracking` or `Mess_Management`) to prevent circular import errors at startup.

### Serializers & Swagger (`drf-spectacular`)
- `COMPONENT_SPLIT_REQUEST = True` is enabled in `Mess_Mate_Project/settings.py`.
- Mark server-populated fields (`id`, `mess`, `add_by`, `created_at`, `deposit_date`, `utility_date`, computed properties) in `read_only_fields`.
- For file/image uploads in Swagger, use `SwaggerImageField` (`@extend_schema_field(OpenApiTypes.BINARY)`) and set `parser_classes = [MultiPartParser, FormParser, JSONParser]` with `request={"multipart/form-data": Serializer}` in `@extend_schema`.

### Notifications
- Store all in-app notifications in `Mess_Management.Notification`.
- **Always exclude the actor** (`by_user`) from receiving notifications for their own action.
- Use `Notification.objects.bulk_create(...)` for mess-wide broadcasts.

---

## 4. Domain Rules & Pitfalls to Avoid

- **`MealSchedule` has no date field** — it defines recurring daily slots (Breakfast, Lunch, Dinner). Possible meals over $N$ days = `N × len(schedules)`.
- **Financial field names:**
  - `MemberDeposit`: `amount` (timestamp: `deposit_date`, `section`: `'Bazar'` | `'Utilities'`)
  - `MessBazar`: `product_price` (timestamp: `created_at`) — **not** `amount`
  - `MessUtilities`: `utility_cost` (timestamp: `utility_date`) — **not** `amount`
- **`MessCycle` overlap check:** Two cycles $[A_s, A_e]$ and $[B_s, B_e]$ conflict if $A_s \le B_e$ and $A_e \ge B_s$. Always validate via `validate_cycle_conflict()`.
- **Sole Manager Leaving:** A manager cannot leave a mess via `LeaveMessView` if other members remain and no other manager exists; they must call `SwitchMessManagerView` first.
