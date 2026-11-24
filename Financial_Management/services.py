from datetime import timedelta
from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import MessCycle, MemberDeposit, MessBazar, MessUtilities


# ──────────────────────────────────────────────────────────────────────────────
# Cycle conflict helpers
# ──────────────────────────────────────────────────────────────────────────────

def get_conflicting_cycles(mess, start_date, end_date, exclude_id=None):
    qs = MessCycle.objects.filter(
        mess=mess,
        start_date__lte=end_date,
        end_date__gte=start_date,
    )
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    return qs


def validate_cycle_conflict(mess, start_date, end_date, exclude_id=None):
    if not start_date or not end_date:
        return

    if end_date <= start_date:
        raise ValidationError({'end_date': 'End date must be after start date.'})

    conflicts = get_conflicting_cycles(mess, start_date, end_date, exclude_id=exclude_id)
    if conflicts.exists():
        conflicting = conflicts.first()
        start_str = conflicting.start_date.strftime('%Y-%m-%d %H:%M')
        end_str = conflicting.end_date.strftime('%Y-%m-%d %H:%M')
        raise ValidationError({
            'conflict': (
                f"Cycle dates conflict with existing cycle '{conflicting.name}' "
                f"({start_str} to {end_str})."
            )
        })


def create_mess_cycle(mess, name, start_date, end_date):
    validate_cycle_conflict(mess, start_date, end_date)
    return MessCycle.objects.create(
        mess=mess,
        name=name,
        start_date=start_date,
        end_date=end_date,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Cycle meal summary  (meals eaten / possible per member)
# ──────────────────────────────────────────────────────────────────────────────

def cycle_meal_summary(mess, cycle):
    """
    Total meals eaten / possible within a MessCycle — per member and overall.

    Logic:
      - Each day × each MealSchedule slot = 1 possible meal.
      - A slot is NOT eaten when covered by MealOff (mess-wide) OR MealBreak (personal).
      - Members who had not yet joined on a given day also don't eat.
      - Counts only up to today (cycle may still be ongoing).

    Returns dict:
        {
            'cycle_id', 'cycle_name', 'start_date', 'end_date',
            'total_possible',          # days × num_meal_slots
            'overall_eaten',
            'members': [
                {
                    'member_id', 'name', 'is_manager',
                    'total', 'eaten', 'meal_off', 'break', 'not_joined'
                },
                ...
            ],
        }
    """
    # Lazy imports to avoid circular dependency at module load time
    from Meal_Tracking.services import mess_meals, bounds, covers
    from Meal_Tracking.models import MealBreak, MealOff
    from Mess_Management.models import Mess_Members

    meals = mess_meals(mess.id)
    if not meals:
        raise ValidationError("No meal schedules configured for this mess.")

    today = timezone.localdate()
    cycle_start = cycle.start_date.date()
    cycle_end = min(today, cycle.end_date.date())

    if cycle_start > cycle_end:
        return {
            'cycle_id': cycle.id,
            'cycle_name': cycle.name,
            'start_date': cycle_start,
            'end_date': cycle_end,
            'total_possible': 0,
            'members': [],
            'overall_eaten': 0,
        }

    num_days = (cycle_end - cycle_start).days + 1
    total_possible = num_days * len(meals)

    # Mess-wide MealOffs overlapping the cycle
    off_qs = MealOff.objects.filter(
        mess=mess,
        start_date__lte=cycle_end,
    ).filter(Q(end_date__isnull=True) | Q(end_date__gte=cycle_start))
    offs = [bounds(o, meals) for o in off_qs]

    # All active members
    members_qs = Mess_Members.objects.filter(mess=mess).select_related('member')

    # MealBreaks per member overlapping the cycle
    break_qs = MealBreak.objects.filter(
        member__mess=mess,
        start_date__lte=cycle_end,
    ).filter(Q(end_date__isnull=True) | Q(end_date__gte=cycle_start)).select_related('member')

    member_breaks: dict[int, list] = {}
    for br in break_qs:
        member_breaks.setdefault(br.member_id, []).append(bounds(br, meals))

    result_members = []
    overall_eaten = 0

    for mb in members_qs:
        joined_on = timezone.localtime(mb.joined_at).date()
        my_breaks = member_breaks.get(mb.id, [])

        eaten = not_joined = meal_off_count = break_count = 0
        day = cycle_start

        while day <= cycle_end:
            for i, m in enumerate(meals):
                pos = (day, i)
                if any(covers(s, e, pos) for s, e in offs):
                    meal_off_count += 1
                elif day < joined_on:
                    not_joined += 1
                elif any(covers(s, e, pos) for s, e in my_breaks):
                    break_count += 1
                else:
                    eaten += 1
            day += timedelta(days=1)

        user = mb.member
        result_members.append({
            'member_id': mb.id,
            'name': getattr(user, 'name', None) or user.email,
            'is_manager': mb.is_manager,
            'total': num_days * len(meals),
            'eaten': eaten,
            'meal_off': meal_off_count,
            'break': break_count,
            'not_joined': not_joined,
        })
        overall_eaten += eaten

    return {
        'cycle_id': cycle.id,
        'cycle_name': cycle.name,
        'start_date': cycle_start,
        'end_date': cycle_end,
        'total_possible': total_possible,
        'members': result_members,
        'overall_eaten': overall_eaten,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Cycle financial summary  (deposits / bazar / utilities within cycle dates)
# ──────────────────────────────────────────────────────────────────────────────

def cycle_financial_summary(mess, cycle, total_meals_eaten=0):
    """
    Financial totals scoped to a MessCycle date range.

    Field name reference (from models):
      MemberDeposit : amount        (deposit_date)   section = 'Bazar' | 'Utilities'
      MessBazar     : product_price (created_at)     ← NOT 'amount'
      MessUtilities : utility_cost  (utility_date)   ← NOT 'amount'

    Args:
        total_meals_eaten: pass overall_eaten from cycle_meal_summary()
                           to get per_meal_cost; leave 0 to skip.
    """
    start = cycle.start_date
    end = cycle.end_date

    base_qs = MemberDeposit.objects.filter(
        member__mess=mess, deposit_date__range=(start, end)
    )
    total_bazar_deposits = (
        base_qs.filter(section='Bazar')
        .aggregate(total=Sum('amount'))['total'] or 0
    )
    total_utilities_deposits = (
        base_qs.filter(section='Utilities')
        .aggregate(total=Sum('amount'))['total'] or 0
    )

    total_bazar = (
        MessBazar.objects
        .filter(mess=mess, created_at__range=(start, end))
        .aggregate(total=Sum('product_price'))['total'] or 0
    )

    total_utilities = (
        MessUtilities.objects
        .filter(mess=mess, utility_date__range=(start, end))
        .aggregate(total=Sum('utility_cost'))['total'] or 0
    )

    bazar_balance     = total_bazar_deposits - total_bazar
    utilities_balance = total_utilities_deposits - total_utilities
    per_meal_cost     = round(total_bazar / total_meals_eaten, 2) if total_meals_eaten > 0 else None

    return {
        'cycle_id': cycle.id,
        'cycle_name': cycle.name,
        'start_date': start,
        'end_date': end,
        'total_bazar_deposits': total_bazar_deposits,
        'total_utilities_deposits': total_utilities_deposits,
        'total_deposits': total_bazar_deposits + total_utilities_deposits,
        'total_bazar': total_bazar,
        'total_utilities': total_utilities,
        'bazar_balance': bazar_balance,
        'utilities_balance': utilities_balance,
        'overall_balance': bazar_balance + utilities_balance,
        'total_meals_eaten': total_meals_eaten,
        'per_meal_cost': per_meal_cost,
    }
