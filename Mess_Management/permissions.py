from rest_framework.permissions import BasePermission
from .models import Mess_Members
from .services import VERIFIED_FIELD


class IsVerifiedUser(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and getattr(request.user, VERIFIED_FIELD, False))


class IsMessManager(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        mess_id = view.kwargs.get('mess_id')
        if not mess_id:
            return False
        return Mess_Members.objects.filter(
            member=request.user,
            mess_id=mess_id,
            is_manager=True
        ).exists()


class IsMessMember(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        mess_id = view.kwargs.get('mess_id')
        if not mess_id:
            return False
        return Mess_Members.objects.filter(
            member=request.user,
            mess_id=mess_id
        ).exists()