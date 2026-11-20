from django.contrib import admin
from .models import NBCQuarterlyPlacement, MonthlyRebateAccrual, MonthlyHealthCheck

@admin.register(NBCQuarterlyPlacement)
class NBCQuarterlyPlacementAdmin(admin.ModelAdmin):
    list_display = ('depot', 'year', 'quarter', 'qualifying_cases', 'category', 'calculated_at')
    list_filter = ('year', 'quarter', 'category', 'depot')
    readonly_fields = ('calculated_at',)

@admin.register(MonthlyRebateAccrual)
class MonthlyRebateAccrualAdmin(admin.ModelAdmin):
    list_display = ('depot', 'year', 'month', 'product_category', 'qualifying_cases', 'rebate_rate', 'estimated_amount', 'status')
    list_filter = ('year', 'month', 'product_category', 'status', 'depot')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(MonthlyHealthCheck)
class MonthlyHealthCheckAdmin(admin.ModelAdmin):
    list_display = ('depot', 'year', 'month', 'bank_balance', 'grand_total_stock_value', 'credit_exposure_balance', 'completed_at')
    list_filter = ('year', 'month', 'depot')
    readonly_fields = ('completed_at', 'created_at', 'updated_at')
