from django.contrib import admin
from .models import MemberDeposit, MessBazar, MessUtilities, MessCycle
# Register your models here.

@admin.register(MemberDeposit)
class MemberDepositAdmin(admin.ModelAdmin):
    list_display = ('id', 'member','add_by', 'amount', 'section', 'deposit_date')
    search_fields = ('member__member__email',)
    list_filter = ('deposit_date',)
    ordering = ('-deposit_date',)

@admin.register(MessBazar)
class MessBazarAdmin(admin.ModelAdmin):
    list_display = ('id', 'mess', 'member', 'product_name', 'product_quantity', 'product_price', 'created_at')
    search_fields = ('mess__name', 'member__member__email', 'product_name')
    list_filter = ('created_at',)
    ordering = ('-created_at',)

@admin.register(MessUtilities)
class MessUtilitiesAdmin(admin.ModelAdmin):
    list_display = ('id', 'mess', 'utility_name', 'description', 'utility_cost', 'utility_date')
    search_fields = ('mess__name', 'utility_name')
    list_filter = ('utility_date',)
    ordering = ('-utility_date',)

@admin.register(MessCycle)
class MessCycleAdmin(admin.ModelAdmin):
    list_display = ('id', 'mess', 'name', 'start_date', 'end_date')
    search_fields = ('mess__name', 'name')
    list_filter = ('mess', 'start_date', 'end_date')
    ordering = ('-start_date',)
