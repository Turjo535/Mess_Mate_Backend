from django.utils import timezone
from rest_framework import serializers
from .models import MealBreak, MealOff, MealSchedule
from .services import check_time_limit, make_bounds, mess_meals, validated_bounds


class MealScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = MealSchedule
        fields = ['id', 'meal_type', 'meal_time', 'meal_select_time']
        extra_kwargs = {'meal_time': {'required': True, 'allow_null': False}}  # ক্রম এই সময় থেকেই আসে

    def validate(self, attrs):
        t = attrs.get('meal_time', getattr(self.instance, 'meal_time', None))
        s = attrs.get('meal_select_time', getattr(self.instance, 'meal_select_time', None))
        if t and s and s > t:
            raise serializers.ValidationError("meal_select_time must be before meal_time.")
        return attrs


class RangeSerializer(serializers.ModelSerializer):
    start_meal = serializers.PrimaryKeyRelatedField(
        queryset=MealSchedule.objects.all(), required=False, allow_null=True)
    end_meal = serializers.PrimaryKeyRelatedField(
        queryset=MealSchedule.objects.all(), required=False, allow_null=True)
    mode = 'member'
    max_days = 90
    end_required = False

    def validate(self, attrs):
        mess_id = self.context['mess_id']
        sm, em = attrs.get('start_meal'), attrs.get('end_meal')
        if any(m and m.mess_id != mess_id for m in (sm, em)):
            raise serializers.ValidationError("Meal does not belong to this mess.")
        if self.end_required and not attrs.get('end_date'):
            attrs['end_date'] = attrs['start_date']
        if em and not attrs.get('end_date'):
            raise serializers.ValidationError("end_meal needs end_date.")
        if attrs['start_date'] < timezone.localdate():
            raise serializers.ValidationError("Cannot start in the past.")
        meals = mess_meals(mess_id)
        if not meals:
            raise serializers.ValidationError("Create meal schedules first.")

        start, end = validated_bounds(attrs, meals)
        if end and end < start:
            raise serializers.ValidationError("End is before start.")
        if end and (end[0] - start[0]).days > self.max_days:
            raise serializers.ValidationError(f"Cannot be longer than {self.max_days + 1} days.")
        check_time_limit(start, end, meals, self.mode)
        return attrs


class MealBreakSerializer(RangeSerializer):
    class Meta:
        model = MealBreak
        fields = ['id', 'start_date', 'start_meal', 'end_date', 'end_meal', 'reason']


class MealOffSerializer(RangeSerializer):
    mode = 'manager'
    max_days = 30
    end_required = True

    class Meta:
        model = MealOff
        fields = ['id', 'start_date', 'start_meal', 'end_date', 'end_meal', 'reason']


class ResumeSerializer(serializers.Serializer):
    """'এই সময় থেকে আবার খাব।' to_date না দিলে বিরতির শেষ পর্যন্ত, দিলে শুধু সেই পরিসীমা।"""
    from_date = serializers.DateField()
    from_meal = serializers.PrimaryKeyRelatedField(
        queryset=MealSchedule.objects.all(), required=False, allow_null=True)
    to_date = serializers.DateField(required=False, allow_null=True)
    to_meal = serializers.PrimaryKeyRelatedField(
        queryset=MealSchedule.objects.all(), required=False, allow_null=True)

    def validate(self, attrs):
        mess_id = self.context['mess_id']
        fm, tm, td = attrs.get('from_meal'), attrs.get('to_meal'), attrs.get('to_date')
        if any(m and m.mess_id != mess_id for m in (fm, tm)):
            raise serializers.ValidationError("Meal does not belong to this mess.")
        if tm and not td:
            raise serializers.ValidationError("to_meal needs to_date.")
        if attrs['from_date'] < timezone.localdate():
            raise serializers.ValidationError("Past date not allowed.")
        meals = mess_meals(mess_id)
        if not meals:
            raise serializers.ValidationError("Create meal schedules first.")
        start, end = make_bounds(attrs['from_date'], fm.id if fm else None,
                                 td, tm.id if tm else None, meals)
        if end and end < start:
            raise serializers.ValidationError("End is before start.")
        check_time_limit(start, end, meals, self.context.get('mode', 'member'))
        attrs['_start'], attrs['_end'], attrs['_meals'] = start, end, meals
        return attrs

class ReportQuerySerializer(serializers.Serializer):
    start_date = serializers.DateField()
    end_date = serializers.DateField()

    def validate(self, attrs):
        if attrs['end_date'] < attrs['start_date']:
            raise serializers.ValidationError("end_date is before start_date.")
        if (attrs['end_date'] - attrs['start_date']).days > 92:
            raise serializers.ValidationError("Range cannot be longer than 93 days.")
        return attrs


class ReportMealSerializer(serializers.Serializer):
    meal_id = serializers.IntegerField()
    meal_type = serializers.CharField()
    meal_time = serializers.TimeField(allow_null=True)
    eating = serializers.BooleanField()
    reason = serializers.ChoiceField(choices=['meal_off', 'not_joined', 'break'], allow_null=True)


class ReportDaySerializer(serializers.Serializer):
    date = serializers.DateField()
    eaten = serializers.IntegerField()
    not_eaten = serializers.IntegerField()
    meals = ReportMealSerializer(many=True)


class ReportMealTotalSerializer(serializers.Serializer):
    meal_id = serializers.IntegerField()
    meal_type = serializers.CharField()
    eaten = serializers.IntegerField()
    not_eaten = serializers.IntegerField()


class ReportSummarySerializer(serializers.Serializer):
    total_meals = serializers.IntegerField()
    eaten = serializers.IntegerField()
    not_eaten = serializers.IntegerField()
    by_reason = serializers.DictField(child=serializers.IntegerField())
    by_meal = ReportMealTotalSerializer(many=True)


class MemberMealReportSerializer(serializers.Serializer):
    member = serializers.DictField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    summary = ReportSummarySerializer()
    days = ReportDaySerializer(many=True)


class MemberBriefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    is_manager = serializers.BooleanField()
# ---- Swagger response shapes ----
class ScheduleStatusSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    meal_type = serializers.CharField()
    meal_time = serializers.TimeField(allow_null=True)
    eating = serializers.BooleanField()
    total_eating = serializers.IntegerField()
    meal_off = serializers.BooleanField()


class MealsDaySerializer(serializers.Serializer):
    date = serializers.DateField()
    schedules = ScheduleStatusSerializer(many=True)


class OverlapSerializer(serializers.Serializer):
    detail = serializers.CharField()
    overlaps = serializers.ListField(child=serializers.DictField())