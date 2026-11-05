from django.urls import path
from . import views as v

urlpatterns = [
    path('create-mess/', v.CreateMessView.as_view()),
    path('<int:mess_id>/invitations/', v.MessInvitationListCreateView.as_view()),
    path('<int:mess_id>/invitations/<int:pk>/', v.MessInvitationCancelView.as_view()),
    path('invitations/', v.MyInvitationListView.as_view()),
    path('invitations/lookup/', v.InvitationLookupView.as_view()),
    path('invitations/<int:pk>/', v.InvitationRespondView.as_view()),
    path('notifications/', v.NotificationListView.as_view()),
    path('notifications/<int:pk>/', v.NotificationReadView.as_view()),
]