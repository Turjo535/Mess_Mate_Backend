from datetime import timedelta
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import MessCycle
from Meal_Tracking.services import mess_meals, bounds, covers, make_bounds, validated_bounds, check_time_limit, last_started, member_meal_report
from Meal_Tracking.models import MealBreak, MealOff
from Mess_Management.models import Mess_Members


def get_conflicting_cycles(mess, start_date, end_date, exclude_id=None):
    
    qs = MessCycle.objects.filter(
        mess=mess,
        start_date__lte=end_date,
        end_date__gte=start_date
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
            'conflict': f"Cycle dates conflict with existing cycle '{conflicting.name}' ({start_str} to {end_str})."
        })


def create_mess_cycle(mess, name, start_date, end_date):
    
    validate_cycle_conflict(mess, start_date, end_date)
    return MessCycle.objects.create(
        mess=mess,
        name=name,
        start_date=start_date,
        end_date=end_date
    )


# ──────────────────────────────────────────────────────────────────────────────
# Cycle meal summary
# ──────────────────────────────────────────────────────────────────────────────

def get_cycle_meal_summary(cycle_id,mess_id):
    start_date = MessCycle.objects.get(id=cycle_id).start_date
    end_date = MessCycle.objects.get(id=cycle_id).end_date
    members = Mess_Members.objects.filter(mess_id=mess_id)
    total_meals=0
    


