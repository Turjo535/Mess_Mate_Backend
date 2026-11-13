from collections import defaultdict
from datetime import date, timedelta
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from Mess_Management.models import Mess_Members, Notification
from .models import MealBreak, MealOff, MealSchedule

INF = (date.max, 0)


# ------------------------------------------------ অবস্থান (তারিখ, বেলার ক্রম)
def mess_meals(mess_id):
    return list(MealSchedule.objects.filter(mess_id=mess_id).order_by('meal_time', 'id'))


def make_bounds(start_date, start_meal_id, end_date, end_meal_id, meals):
    index = {m.id: i for i, m in enumerate(meals)}
    start = (start_date, index[start_meal_id] if start_meal_id else 0)
    end = None
    if end_date:
        end = (end_date, index[end_meal_id] if end_meal_id else len(meals) - 1)
    return start, end                      # end None = চলতে থাকবে


def bounds(r, meals):
    return make_bounds(r.start_date, r.start_meal_id, r.end_date, r.end_meal_id, meals)


def validated_bounds(v, meals):
    sm, em = v.get('start_meal'), v.get('end_meal')
    return make_bounds(v['start_date'], sm.id if sm else None,
                       v.get('end_date'), em.id if em else None, meals)


def covers(start, end, pos):
    return start <= pos and (end is None or pos <= end)


def step(pos, delta, n):
    d, i = pos
    i += delta
    if i >= n:
        return (d + timedelta(days=1), 0)
    if i < 0:
        return (d - timedelta(days=1), n - 1)
    return (d, i)


def label(pos, meals):
    if pos is None or pos == INF:
        return 'ongoing'
    return {'date': pos[0].isoformat(), 'meal': meals[pos[1]].meal_type}


# ------------------------------------------------ Overlap
def find_overlaps(start, end, qs, meals):
    """নতুন পরিসীমা (start, end)-এর সাথে qs-এর যেগুলো মেলে, সেগুলোর বিবরণ।"""
    qs = qs.filter(Q(end_date__isnull=True) | Q(end_date__gte=start[0]))
    if end:
        qs = qs.filter(start_date__lte=end[0])
    new_end, out = end or INF, []
    for r in qs:
        s, e = bounds(r, meals)
        lo, hi = max(start, s), min(new_end, e or INF)
        if lo <= hi:
            out.append({'id': r.id,
                        'existing': {'from': label(s, meals), 'to': label(e, meals)},
                        'overlap': {'from': label(lo, meals), 'to': label(hi, meals)}})
    return out


# ------------------------------------------------ সময়সীমা (আজকের বেলা)
def check_time_limit(start, end, meals, mode):
    """পরিসীমার ভেতরে আজকের কোনো বেলার সময় পেরিয়ে গেলে বদলানো যাবে না।
    mode='member': meal_select_time (না থাকলে meal_time), mode='manager': meal_time।"""
    today, now = timezone.localdate(), timezone.localtime().time()
    late = []
    for i, m in enumerate(meals):
        if covers(start, end, (today, i)):
            limit = (m.meal_select_time or m.meal_time) if mode == 'member' else m.meal_time
            if limit and now >= limit:
                late.append(m.meal_type)
    if late:
        raise ValidationError(f"Too late to change today's meal: {', '.join(late)}.")


# ------------------------------------------------ কে খাবে
def _alive(model, day, **filters):
    return (model.objects.filter(start_date__lte=day, **filters)
            .filter(Q(end_date__isnull=True) | Q(end_date__gte=day)))


def eating_map(mess, day):
    """(meals, মেসের তরফে বন্ধ বেলার id-এর সেট, {(meal_id, member_id): খাবে কিনা})
    ক্রম: মেসের মিল অফ > যোগ দেওয়ার আগে > নিজের বিরতি > ডিফল্ট খাবে।"""
    meals = mess_meals(mess.id)
    members = list(Mess_Members.objects.filter(mess=mess))
    offs = [bounds(o, meals) for o in _alive(MealOff, day, mess=mess)]
    mine = defaultdict(list)
    for b in _alive(MealBreak, day, member__mess=mess):
        mine[b.member_id].append(bounds(b, meals))

    closed = {m.id for i, m in enumerate(meals)
              if any(covers(s, e, (day, i)) for s, e in offs)}
    result = {}
    for mb in members:
        joined = timezone.localtime(mb.joined_at).date() <= day
        for i, m in enumerate(meals):
            personal = any(covers(s, e, (day, i)) for s, e in mine[mb.id])
            result[(m.id, mb.id)] = joined and m.id not in closed and not personal
    return meals, closed, result


# ------------------------------------------------ বিরতি থেকে অংশ বাদ (resume)
def make_range(model, start, end, meals, **fields):
    n = len(meals)
    return model.objects.create(
        start_date=start[0],
        start_meal=meals[start[1]] if start[1] > 0 else None,
        end_date=end[0] if end else None,
        end_meal=meals[end[1]] if end and end[1] < n - 1 else None,
        **fields)


@transaction.atomic
def carve(qs, start, end, meals, copy=('reason',)):
    """qs-এর পরিসীমাগুলো থেকে [start, end] অংশ কেটে বাদ দেয়। বাদ পড়া অংশের তালিকা ফেরত দেয়।"""
    n = len(meals)
    qs = qs.select_for_update().filter(Q(end_date__isnull=True) | Q(end_date__gte=start[0]))
    if end:
        qs = qs.filter(start_date__lte=end[0])
    removed = []
    for r in qs:
        rstart, rend = bounds(r, meals)
        lo, hi = max(start, rstart), min(end or INF, rend or INF)
        if lo > hi:
            continue
        keep = []
        if rstart < start:
            keep.append((rstart, step(start, -1, n)))
        if end is not None and (rend is None or end < rend):
            keep.append((step(end, 1, n), rend))
        fields = {}
        for name in copy:
            attr = r._meta.get_field(name).attname
            fields[attr] = getattr(r, attr)
        model = type(r)
        r.delete()
        for kstart, kend in keep:
            make_range(model, kstart, kend, meals, **fields)
        removed.append((lo, hi))
    return removed


def notify_range(mess, by_user_id, type_, start, end, meals, reason=''):
    payload = {'mess_id': mess.id, 'mess_name': mess.name, 'reason': reason,
               'from': label(start, meals), 'to': label(end, meals)}
    user_ids = (Mess_Members.objects.filter(mess=mess)
                .exclude(member_id=by_user_id).values_list('member_id', flat=True))
    Notification.objects.bulk_create(
        [Notification(user_id=u, type=type_, payload=payload) for u in user_ids])


def notify_meal_off(off, meals, type_='meal_off'):
    s, e = bounds(off, meals)
    notify_range(off.mess, off.created_by_id, type_, s, e, meals, off.reason)

REASONS = ('meal_off', 'not_joined', 'break')



def member_meal_report(mess, member, first, last):
    meals = mess_meals(mess.id)
    if not meals:
        raise ValidationError("Create meal schedules first.")

    def alive(qs):
        qs = qs.filter(start_date__lte=last).filter(Q(end_date__isnull=True) | Q(end_date__gte=first))
        return [bounds(r, meals) for r in qs]

    offs = alive(MealOff.objects.filter(mess=mess))
    mine = alive(MealBreak.objects.filter(member=member))
    joined_on = timezone.localtime(member.joined_at).date()

    by_meal = {m.id: {'meal_id': m.id, 'meal_type': m.meal_type, 'eaten': 0, 'not_eaten': 0}
               for m in meals}
    by_reason = dict.fromkeys(REASONS, 0)
    days, eaten, day = [], 0, first
    while day <= last:
        row, day_eaten = [], 0
        for i, m in enumerate(meals):
            pos = (day, i)
            if any(covers(s, e, pos) for s, e in offs):
                reason = 'meal_off'
            elif day < joined_on:
                reason = 'not_joined'
            elif any(covers(s, e, pos) for s, e in mine):
                reason = 'break'
            else:
                reason = None
            if reason is None:
                day_eaten += 1
                by_meal[m.id]['eaten'] += 1
            else:
                by_reason[reason] += 1
                by_meal[m.id]['not_eaten'] += 1
            row.append({'meal_id': m.id, 'meal_type': m.meal_type, 'meal_time': m.meal_time,
                        'eating': reason is None, 'reason': reason})
        days.append({'date': day, 'eaten': day_eaten,
                     'not_eaten': len(meals) - day_eaten, 'meals': row})
        eaten += day_eaten
        day += timedelta(days=1)

    total = len(days) * len(meals)
    user = member.member
    return {
        'member': {'id': member.id, 'name': getattr(user, 'name', None) or user.email,
                   'is_manager': member.is_manager},
        'start_date': first, 'end_date': last,
        'summary': {'total_meals': total, 'eaten': eaten, 'not_eaten': total - eaten,
                    'by_reason': by_reason, 'by_meal': list(by_meal.values())},
        'days': days}