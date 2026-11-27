# Project Skills — Mess Mate Backend

Reusable implementation patterns and workflows for this repository.

---

## Skill 1: Adding a Mess-Scoped Endpoint

1. **Permission:** Choose `IsMessMember` or `IsMessManager` from `Mess_Management/permissions.py` (always after `IsAuthenticated`).
2. **View:** Resolve `mess = get_object_or_404(Mess, pk=mess_id)`.
3. **Schema:** Add `@extend_schema(tags=[TAG], request=..., responses={...})`.
4. **Route:** Register in `<app>/urls.py` under `<int:mess_id>/...`.
5. **Verify:** Run `python3 -m py_compile` on edited files and test via `docker exec mess_mate_web python manage.py test <app>`.

---

## Skill 2: Sending In-App Notifications

### Financial Management (`Financial_Management/services.py`)
```python
from .services import notify_mess

notify_mess(mess, request.user, 'bazar_added', {
    'bazar_id': bazar.id,
    'product_name': bazar.product_name,
    'product_price': str(bazar.product_price),
    'by': request.user.email,
})
```
- Automatically injects `mess_id` and `mess_name`.
- Excludes `request.user` and bulk-creates `Notification` rows for all other members.

### Mess Management (`Mess_Management/services.py`)
```python
from .services import notify_all_members

notify_all_members(mess, 'member_joined', {
    'mess_id': mess.id,
    'mess_name': mess.name,
    'email': user.email,
    'user_id': user.id,
    'name': getattr(user, 'name', None) or user.email,
}, exclude_user=user)
```

### Meal Tracking (`Meal_Tracking/services.py`)
- `notify_meal_off(off, meals, type_='meal_off')` — broadcasts mess-wide meal-off changes.
- `notify_range(mess, by_user_id, type_, start, end, meals, reason='')` — broadcasts carved/resumed ranges.
- `notify_member(member, type_, start, end, meals, reason='')` — notifies a specific member.

---

## Skill 3: Calculating Cycle Meal & Financial Summaries

Located in `Financial_Management/services.py`:
1. Call `meals = cycle_meal_summary(mess, cycle)` first:
   - Caps `cycle_end = min(today, cycle.end_date.date())`.
   - Evaluates each `(day, meal_index)` slot in priority order:
     1. `MealOff` (mess-wide) → `meal_off`
     2. `day < joined_at.date()` → `not_joined`
     3. `MealBreak` (personal) → `break`
     4. Otherwise → `eaten`
2. Pass `meals['overall_eaten']` into `cycle_financial_summary(mess, cycle, total_meals_eaten=meals['overall_eaten'])`:
   - Splits `MemberDeposit` by `section='Bazar'` vs `section='Utilities'`.
   - Computes `bazar_balance`, `utilities_balance`, `overall_balance`, and `per_meal_cost = round(total_bazar / total_meals_eaten, 2)`.

---

## Skill 4: Handling Image Uploads in Swagger

1. Use `SwaggerImageField` in `serializers.py`:
   ```python
   @extend_schema_field(OpenApiTypes.BINARY)
   class SwaggerImageField(serializers.ImageField):
       pass
   ```
2. Set `parser_classes = [MultiPartParser, FormParser, JSONParser]` on the `APIView`.
3. Annotate the method with `request={"multipart/form-data": MySerializer}` in `@extend_schema`.

---

## Skill 5: Validating Date-Range Overlaps

- **Mess Cycles:** `validate_cycle_conflict(mess, start_date, end_date, exclude_id=None)` in `Financial_Management/services.py`.
- **Meal Breaks / Meal-Offs:** `find_overlaps(start, end, qs, meals)` in `Meal_Tracking/services.py` (returns `409 Conflict` with overlap details on collision).
