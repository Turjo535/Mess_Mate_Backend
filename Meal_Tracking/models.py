from django.db import models
from Mess_Management.models import Mess,Mess_Members
from User_Authentication.models import UserModel
from django.db.models import F, Q
# Create your models here.
class MealSchedule(models.Model):
    mess = models.ForeignKey(Mess, on_delete=models.CASCADE, related_name='meal_schedules')
    meal_type = models.CharField(max_length=50)
    meal_time = models.TimeField(null=True, blank=True) 
    meal_select_time = models.TimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.mess.name} - {self.meal_time} - {self.meal_type}"

class MealRange(models.Model):
    start_date = models.DateField()
    start_meal = models.ForeignKey(MealSchedule, null=True, blank=True,
                                   on_delete=models.PROTECT, related_name='+')
    end_date = models.DateField()          
    end_meal = models.ForeignKey(MealSchedule, null=True, blank=True,
                                 on_delete=models.PROTECT, related_name='+')

    class Meta:
        abstract = True


class MealBreak(MealRange):
    member = models.ForeignKey(Mess_Members, on_delete=models.CASCADE, related_name='meal_breaks')
    reason = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(
            condition=Q(end_date__isnull=True) | Q(end_date__gte=F('start_date')),
            name='break_end_after_start')]
        indexes = [models.Index(fields=['member', 'start_date', 'end_date'])]


class MealOff(MealRange):
    mess = models.ForeignKey(Mess, on_delete=models.CASCADE, related_name='meal_offs')
    reason = models.CharField(max_length=100, blank=True)
    created_by = models.ForeignKey(UserModel, null=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(
            condition=Q(end_date__isnull=True) | Q(end_date__gte=F('start_date')),
            name='mealoff_end_after_start')]
        indexes = [models.Index(fields=['mess', 'start_date', 'end_date'])]