from django.urls import path
from . import views as v

urlpatterns = [
    path('<int:mess_id>/schedules/', v.MealScheduleListCreateView.as_view()),
    path('<int:mess_id>/schedules/<int:pk>/', v.MealScheduleDetailView.as_view()),
    path('<int:mess_id>/meals/', v.MealDayView.as_view()),
    path('<int:mess_id>/breaks/', v.MealBreakListCreateView.as_view()),
    # path('<int:mess_id>/breaks/eat-on/', v.EatOnView.as_view()),
    path('<int:mess_id>/breaks/<int:pk>/', v.MealBreakDeleteView.as_view()),
    path('<int:mess_id>/breaks/resume/', v.MealBreakResumeView.as_view()),
    path('<int:mess_id>/meal-off/', v.MealOffListCreateView.as_view()),
    path('<int:mess_id>/meal-off/resume/', v.MealOffResumeView.as_view()),
    path('<int:mess_id>/meal-off/<int:pk>/', v.MealOffDeleteView.as_view()),
    path('<int:mess_id>/members/', v.MessMemberListView.as_view()),
    path('<int:mess_id>/members/<int:member_id>/meals/', v.MemberMealReportView.as_view()),
]