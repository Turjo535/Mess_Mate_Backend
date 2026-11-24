from django.urls import path
from . import views as V

urlpatterns = [
    # Mess Cycle
    path('<int:mess_id>/mess-cycle/', V.CreateMessCycleView.as_view(), name='mess-cycle'),
    path('<int:mess_id>/mess-cycle/<int:pk>/', V.UpdateMessCycleView.as_view(), name='update-mess-cycle'),

    # Member Deposit
    path('<int:mess_id>/member-deposit/', V.MemberDepositViewSet.as_view(), name='mess-member-deposit'),
    path('<int:mess_id>/member-deposit/<int:pk>/', V.UpdateMemberDepositView.as_view(), name='update-member-deposit'),

    # Mess Bazar
    path('<int:mess_id>/mess-bazar/', V.MessBazarViewSet.as_view(), name='mess-bazar'),
    path('<int:mess_id>/mess-bazar/<int:pk>/', V.UpdateMessBazarView.as_view(), name='update-mess-bazar'),

    # Mess Utilities
    path('<int:mess_id>/mess-utilities/', V.MessUtilitiesViewSet.as_view(), name='mess-utilities'),
    path('<int:mess_id>/mess-utilities/<int:pk>/', V.UpdateMessUtilitiesView.as_view(), name='update-mess-utilities'),

    #financial summary
    path('<int:mess_id>/financial-summary/<int:cycle_id>/', V.MessCycleFinancialSummaryView.as_view(), name='financial-summary'),
]
