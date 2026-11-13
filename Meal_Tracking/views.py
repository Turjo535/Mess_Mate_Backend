from collections import defaultdict
from datetime import date, timedelta
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from Mess_Management.models import Mess, Mess_Members
from Mess_Management.permissions import IsMessManager, IsMessMember
from .models import MealBreak, MealOff, MealSchedule
from django.db.models import ProtectedError, Q
from rest_framework.exceptions import PermissionDenied, ValidationError
from .serializers import (MealBreakSerializer, MealOffSerializer, MealScheduleSerializer,
                          MealsDaySerializer, MemberBriefSerializer, MemberMealReportSerializer,
                          OverlapSerializer, ReportQuerySerializer, ResumeSerializer)
from .services import (bounds, carve, check_time_limit, eating_map, find_overlaps,
                       member_meal_report, mess_meals, notify_meal_off, notify_range,
                       validated_bounds)

TAG = 'Meal Tracking'
WRITE = ('POST', 'PATCH', 'DELETE')


def get_member(request, mess_id):
    return get_object_or_404(Mess_Members, member=request.user, mess_id=mess_id)


def own_breaks(request, mess_id):
    return MealBreak.objects.filter(member__member=request.user, member__mess_id=mess_id)


class MemberView(APIView):
    permission_classes = [IsAuthenticated, IsMessMember]


class ManagerWriteView(APIView):
    """GET: member, POST/PATCH/DELETE: manager"""

    def get_permissions(self):
        perm = IsMessManager if self.request.method in WRITE else IsMessMember
        return [IsAuthenticated(), perm()]


# ---------------------------------------------------------------- বেলা (Schedule)
class MealScheduleListCreateView(ManagerWriteView):
    @extend_schema(tags=[TAG], responses={200: MealScheduleSerializer(many=True)})
    def get(self, request, mess_id):
        schedules = MealSchedule.objects.filter(mess_id=mess_id)
        return Response(MealScheduleSerializer(schedules, many=True).data)

    @extend_schema(tags=[TAG], request=MealScheduleSerializer, responses={201: MealScheduleSerializer})
    def post(self, request, mess_id):
        mess = get_object_or_404(Mess, pk=mess_id)
        s = MealScheduleSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        s.save(mess=mess)
        return Response(s.data, status=status.HTTP_201_CREATED)


class MealScheduleDetailView(ManagerWriteView):
    def get_schedule(self, mess_id, pk):
        return get_object_or_404(MealSchedule, pk=pk, mess_id=mess_id)

    @extend_schema(tags=[TAG], responses={200: MealScheduleSerializer})
    def get(self, request, mess_id, pk):
        return Response(MealScheduleSerializer(self.get_schedule(mess_id, pk)).data)

    @extend_schema(tags=[TAG], request=MealScheduleSerializer, responses={200: MealScheduleSerializer})
    def patch(self, request, mess_id, pk):
        s = MealScheduleSerializer(self.get_schedule(mess_id, pk), data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data)

    @extend_schema(tags=[TAG], responses={204: None})
    def delete(self, request, mess_id, pk):
        schedule = self.get_schedule(mess_id, pk)
        try:
            schedule.delete()
        except ProtectedError:
            raise ValidationError('This meal is used in breaks or meal-offs. Remove them first.')
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- দিনের অবস্থা
class MealDayView(MemberView):
    @extend_schema(tags=[TAG], parameters=[OpenApiParameter('date', OpenApiTypes.DATE, required=False)],
                   responses={200: MealsDaySerializer})
    def get(self, request, mess_id):
        raw = request.query_params.get('date')
        try:
            day = date.fromisoformat(raw) if raw else timezone.localdate()
        except ValueError:
            raise ValidationError({'date': 'Use YYYY-MM-DD.'})

        mess = get_object_or_404(Mess, pk=mess_id)
        me = get_member(request, mess_id)
        schedules, off, eating = eating_map(mess, day)
        totals = defaultdict(int)
        for (schedule_id, _), value in eating.items():
            totals[schedule_id] += value
        return Response({'date': day, 'schedules': [
            {'id': s.id, 'meal_type': s.meal_type, 'meal_time': s.meal_time,
             'eating': eating[(s.id, me.id)], 'total_eating': totals[s.id],
             'meal_off': None in off or s.id in off}
            for s in schedules]})


# ---------------------------------------------------------------- Member-এর বিরতি
class MealBreakListCreateView(MemberView):
    @extend_schema(tags=[TAG], responses={200: MealBreakSerializer(many=True)})
    def get(self, request, mess_id):
        breaks = (own_breaks(request, mess_id)
                  .filter(Q(end_date__isnull=True) | Q(end_date__gte=timezone.localdate()))
                  .order_by('start_date'))
        return Response(MealBreakSerializer(breaks, many=True).data)

    @extend_schema(tags=[TAG], request=MealBreakSerializer,
                   responses={201: MealBreakSerializer, 409: OverlapSerializer})
    def post(self, request, mess_id):
        member = get_member(request, mess_id)
        s = MealBreakSerializer(data=request.data, context={'mess_id': mess_id})
        s.is_valid(raise_exception=True)
        meals = mess_meals(mess_id)
        start, end = validated_bounds(s.validated_data, meals)
        overlaps = find_overlaps(start, end, MealBreak.objects.filter(member=member), meals)
        if overlaps:
            return Response({'detail': 'Overlaps with your existing break.', 'overlaps': overlaps},
                            status=status.HTTP_409_CONFLICT)
        s.save(member=member)
        return Response(s.data, status=status.HTTP_201_CREATED)


class MealBreakDeleteView(MemberView):
    @extend_schema(tags=[TAG], responses={204: None})
    def delete(self, request, mess_id, pk):
        brk = get_object_or_404(own_breaks(request, mess_id), pk=pk)
        if brk.start_date <= timezone.localdate():
            raise ValidationError('Break already started. Use resume instead.')
        brk.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MealBreakResumeView(MemberView):
    @extend_schema(tags=[TAG], request=ResumeSerializer, responses={200: None})
    def post(self, request, mess_id):
        member = get_member(request, mess_id)
        s = ResumeSerializer(data=request.data, context={'mess_id': mess_id})
        s.is_valid(raise_exception=True)
        v = s.validated_data
        removed = carve(MealBreak.objects.filter(member=member), v['_start'], v['_end'],
                        v['_meals'], ('member', 'reason'))
        if not removed:
            raise ValidationError('No break found in this period.')
        return Response({'detail': 'Updated.'})





# ---------------------------------------------------------------- ম্যানেজারের মিল অফ
class MealOffListCreateView(ManagerWriteView):
    @extend_schema(tags=[TAG], responses={200: MealOffSerializer(many=True)})
    def get(self, request, mess_id):
        offs = (MealOff.objects.filter(mess_id=mess_id, end_date__gte=timezone.localdate())
                .prefetch_related('meal_schedules').order_by('start_date'))
        return Response(MealOffSerializer(offs, many=True).data)

    @extend_schema(tags=[TAG], request=MealOffSerializer,
                   responses={201: MealOffSerializer, 409: OverlapSerializer})
    def post(self, request, mess_id):
        mess = get_object_or_404(Mess, pk=mess_id)
        s = MealOffSerializer(data=request.data, context={'mess_id': mess_id})
        s.is_valid(raise_exception=True)
        meals = mess_meals(mess_id)
        start, end = validated_bounds(s.validated_data, meals)
        overlaps = find_overlaps(start, end, MealOff.objects.filter(mess=mess), meals)
        if overlaps:
            return Response({'detail': 'Overlaps with an existing meal-off.', 'overlaps': overlaps},
                            status=status.HTTP_409_CONFLICT)
        off = s.save(mess=mess, created_by=request.user)
        notify_meal_off(off, meals)
        return Response(s.data, status=status.HTTP_201_CREATED)


class MealOffDeleteView(APIView):
    permission_classes = [IsAuthenticated, IsMessManager]

    @extend_schema(tags=[TAG], responses={204: None})
    def delete(self, request, mess_id, pk):
        off = get_object_or_404(MealOff.objects.select_related('mess'), pk=pk, mess_id=mess_id)
        meals = mess_meals(mess_id)
        start, end = bounds(off, meals)
        if start[0] < timezone.localdate():
            raise ValidationError('Already started. Past meal-off cannot be removed.')
        check_time_limit(start, end, meals, 'manager')
        notify_meal_off(off, meals, 'meal_off_cancelled')
        off.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MealOffResumeView(APIView):
    
    permission_classes = [IsAuthenticated, IsMessManager]

    @extend_schema(tags=[TAG], request=ResumeSerializer, responses={200: None})
    def post(self, request, mess_id):
        mess = get_object_or_404(Mess, pk=mess_id)
        s = ResumeSerializer(data=request.data, context={'mess_id': mess_id, 'mode': 'manager'})
        s.is_valid(raise_exception=True)
        v = s.validated_data
        removed = carve(MealOff.objects.filter(mess=mess), v['_start'], v['_end'],
                        v['_meals'], ('mess', 'reason', 'created_by'))
        if not removed:
            raise ValidationError('No meal-off found in this period.')
        for lo, hi in removed:
            notify_range(mess, request.user.id, 'meal_off_cancelled', lo, hi, v['_meals'])
        return Response({'detail': 'Updated.'})

class MemberMealReportView(MemberView):
    @extend_schema(tags=[TAG], parameters=[ReportQuerySerializer],
                   responses={200: MemberMealReportSerializer})
    def get(self, request, mess_id, member_id):
        me = get_member(request, mess_id)
        target = get_object_or_404(Mess_Members.objects.select_related('member', 'mess'),
                                   pk=member_id, mess_id=mess_id)
        if target.id != me.id and not me.is_manager:
            raise PermissionDenied('You can only view your own meals.')
        q = ReportQuerySerializer(data=request.query_params)
        q.is_valid(raise_exception=True)
        return Response(member_meal_report(target.mess, target,
                                           q.validated_data['start_date'], q.validated_data['end_date']))
    
class MessMemberListView(MemberView):
    @extend_schema(tags=[TAG], responses={200: MemberBriefSerializer(many=True)})
    def get(self, request, mess_id):
        rows = Mess_Members.objects.filter(mess_id=mess_id).select_related('member').order_by('member__name')
        return Response([{'id': r.id, 'name': getattr(r.member, 'name', None) or r.member.email,
                          'is_manager': r.is_manager} for r in rows])