from django.utils import timezone
from rest_framework.permissions import BasePermission
from Mess_Management.models import Mess_Members, Mess
from .models import MessCycle


class IsMessCycleActive(BasePermission):
    def has_permission(self, request, view):
        mess_id = view.kwargs.get('mess_id') or request.query_params.get('mess_id')
        cycle = MessCycle.objects.filter(mess_id=mess_id).last()
        return bool(cycle and cycle.is_active)
