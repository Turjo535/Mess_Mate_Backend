# Project Plan — Mess Mate Backend

**Active Branch:** `notifications`  
**Other Branches:** `main`, `mess_management`, `meal-tracking`, `financial-management`

---

## Completed Milestones

### Phase 1: Authentication & User Profiles (`User_Authentication`)
- [x] Custom `UserModel` (email-based login, profile fields, Firebase `unique_id`)
- [x] Registration with 6-digit email OTP verification (`15m` TTL)
- [x] JWT Sign-In (`access`: 7 days, `refresh`: 10 days)
- [x] Google Sign-In via Firebase Admin SDK (`google_auth`)
- [x] Forgot Password (OTP-verified) & Change Password
- [x] Profile retrieval (`GET /api/auth/user/`) & partial update (`PATCH /api/auth/user/update-profile/`)

### Phase 2: Mess & Membership Management (`Mess_Management`)
- [x] Mess creation (creator auto-assigned as manager)
- [x] Bulk email invitations (in-app notifications for existing users, Celery async emails for new users)
- [x] Invitation lookup, accept/decline, and expiration handling (`INVITE_TTL = 72h`)
- [x] Switch Mess Manager (`POST /api/mess/<mess_id>/switch-manager/`)
- [x] Leave Mess endpoint (`POST /api/mess/<mess_id>/leave/`) with sole-manager guard
- [x] Notifications list & mark-as-read APIs (`GET/PATCH /api/mess/notifications/`)

### Phase 3: Meal Tracking (`Meal_Tracking`)
- [x] Meal schedules CRUD (`MealSchedule`)
- [x] Daily meal status & headcount (`GET /api/meal/<mess_id>/meals/`)
- [x] Personal meal breaks (create with overlap check, delete future, partial resume/carve)
- [x] Mess-wide meal-off (create, delete, partial resume/carve)
- [x] Past meal adjustments by manager (up to 93 days back)
- [x] Per-member meal report (`GET /api/meal/<mess_id>/members/<member_id>/meals/`)

### Phase 4: Financial Management (`Financial_Management`)
- [x] Mess Cycles CRUD with overlap conflict detection + `is_active` / `is_over` properties
- [x] Member Deposits CRUD (`Bazar` / `Utilities` sections)
- [x] Mess Bazar CRUD with image upload (`SwaggerImageField` + multipart schema)
- [x] Mess Utilities CRUD
- [x] Cycle Financial & Meal Summary (`cycle_meal_summary` + `cycle_financial_summary` returning `bazar_balance`, `utilities_balance`, `overall_balance`, `per_meal_cost`)

### Phase 5: Cross-App Notifications & Documentation (`notifications` branch)
- [x] Financial activity notifications (`POST`/`PATCH`/`DELETE` for cycles, deposits, bazar, utilities)
- [x] Meal break notifications (`meal_break_added`, `meal_break_resumed`)
- [x] Member join (`member_joined`) & leave (`member_left`) notifications to all mess members
- [x] Project `README.md`, `agents.md`, `skills.md`, and `plan.md`

---

## Next Steps

1. **Run Full Test Suite in Docker**
   ```bash
   docker exec mess_mate_web python manage.py test -v 2
   ```
2. **Add Missing Unit Tests**
   - `Mess_Management`: `LeaveMessView` (normal leave, sole-manager blocked, `member_left` notification) and `member_joined` notification on invitation accept.
   - `Financial_Management`: `cycle_meal_summary`, `cycle_financial_summary`, and `MessCycleFinancialSummaryView`.
   - `Meal_Tracking`: `meal_break_added` and `meal_break_resumed` notifications.
3. **End-to-End Postman / Swagger Verification**
   - Import `http://localhost:8000/api/schema/` into Postman and verify join, leave, meal break, financial CRUD, and notification flows.
4. **Merge to `main`**
   - Review `git diff` across `notifications`, ensure migrations are clean (`makemigrations --check --dry-run`), and merge into `main`.
