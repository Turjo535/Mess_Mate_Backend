from django.contrib import admin
from .models import UserModel, OTPModel
# Register your models here.

@admin.register(UserModel)
class UserModelAdmin(admin.ModelAdmin):
    list_display = ('id','unique_id', 'email', 'name', 'phone', 'date_of_birth','institution','permanent_address', 'profile_picture', 'profession', 'is_admin', 'is_staff', 'is_active')
    search_fields = ('email', 'name')
    list_filter = ('is_admin', 'is_staff', 'is_active')
    ordering = ('email',)   

@admin.register(OTPModel)
class OTPModelAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'otp', 'created_at')
    search_fields = ('user__email',)
    list_filter = ('created_at',)
    ordering = ('-created_at',)