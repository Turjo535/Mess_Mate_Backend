from django.contrib import admin
from .models import MealSchedule, MealBreak, MealOff
# Register your models here.

@admin.register(MealSchedule)
class MealScheduleAdmin(admin.ModelAdmin):
    list_display = ('id','mess', 'meal_type', 'meal_time', 'meal_select_time', 'created_at')
    list_filter = ('mess', 'meal_type')
    search_fields = ('mess__name', 'meal_type')

# @admin.register(MealRange)
# class MealRangeAdmin(admin.ModelAdmin):
#     list_display = ('id','start_date', 'end_date', 'start_meal', 'end_meal')
#     list_filter = ('start_date', 'end_date')
#     search_fields = ('start_meal__meal_type', 'end_meal__meal_type')

@admin.register(MealBreak)
class MealBreakAdmin(admin.ModelAdmin):
    list_display = ('id','member','start_date', 'end_date','start_meal','end_meal', 'reason', 'created_at')
    list_filter = ('member', 'created_at')
    search_fields = ('member__user__username', 'reason')

@admin.register(MealOff)
class MealOffAdmin(admin.ModelAdmin):
    list_display = ('id','mess', 'reason', 'created_by', 'created_at')
    list_filter = ('mess', 'created_at')
    search_fields = ('mess__name', 'reason', 'created_by__username')
