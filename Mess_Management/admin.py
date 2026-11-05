from django.contrib import admin
from .models import Mess, Mess_Members,MessInvitation, Notification
# Register your models here.

@admin.register(Mess)
class MessAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'mess_address', 'instruction', 'capacity', 'contact_number', 'created_at')
    search_fields = ('name', 'mess_address')
    list_filter = ('capacity',)
    ordering = ('created_at',)
@admin.register(Mess_Members)
class Mess_MembersAdmin(admin.ModelAdmin):
    list_display = ('id', 'member', 'mess', 'is_manager', 'joined_at')
    search_fields = ('member__email', 'mess__name')
    list_filter = ('is_manager', 'joined_at')
    ordering = ('-joined_at',)

@admin.register(MessInvitation)
class MessInvitationAdmin(admin.ModelAdmin):
    list_display = ('id', 'mess', 'invited_email', 'invited_by','token', 'created_at', 'expires_at')
    search_fields = ('invited_email',)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'type', 'is_read', 'created_at')
    list_filter = ('type', 'is_read')