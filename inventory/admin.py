from django.contrib import admin
from .services import record_depot_price_changes
from .models import (
    Product,
    PriceHistory,
    Supplier,
    StockReceipt,
    StockReceiptItem,
    InventoryTransaction,
    Promotion,
    DepotPriceChange,
)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "sku",
        "name",
        "category",
        "package_type",
        "volume",
        "base_cost_price",
        "base_selling_price",
        "is_active",
    )
    search_fields = ("sku", "name")
    list_filter = ("category", "package_type", "is_active")


@admin.register(PriceHistory)
class PriceHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "selling_price",
        "cost_price",
        "effective_from",
        "changed_by",
        "reason",
    )
    list_filter = ("effective_from",)
    search_fields = ("product__sku", "product__name", "reason")
    readonly_fields = (
        "product",
        "cost_price",
        "selling_price",
        "effective_from",
        "changed_by",
        "reason",
    )

    def has_add_permission(self, request):
        # Retired: the price now comes from stock receipts. Old rows are kept
        # for reference only, so nobody can add one that would be ignored.
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        # Preserve historical truth — old prices are never deleted.
        return False


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_person", "phone", "is_active")
    search_fields = ("name",)


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "level",
        "promotion_type",
        "supplier",
        "depot",
        "start_date",
        "end_date",
        "is_active",
    )
    list_filter = ("level", "promotion_type", "is_active", "depot", "supplier")
    search_fields = ("name", "description")
    filter_horizontal = ("products",)
    autocomplete_fields = ("supplier", "depot")


class StockReceiptItemInline(admin.TabularInline):
    model = StockReceiptItem
    extra = 1
    readonly_fields = ()

    def get_readonly_fields(self, request, obj=None):
        # Once a receipt item has been saved (and its inventory
        # transaction posted), the acquisition cost must not be
        # editable — it's the historical record of what was
        # actually paid. New items can still be added freely.
        if obj and obj.pk:
            return ["product", "quantity", "cost_price"]
        return []


@admin.register(StockReceipt)
class StockReceiptAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number",
        "supplier",
        "depot",
        "receipt_date",
        "total_amount",
    )
    list_filter = ("depot", "receipt_date")
    search_fields = ("invoice_number",)
    inlines = [StockReceiptItemInline]

    def get_readonly_fields(self, request, obj=None):
        # invoice_number is referenced as the `reference` string on
        # every InventoryTransaction created from this receipt's
        # items. Editing it after items exist would silently break
        # that traceability link.
        if obj and obj.pk:
            return ["invoice_number"]
        return []

    def save_formset(self, request, form, formset, change):
        if formset.model is not StockReceiptItem:
            return super().save_formset(request, form, formset, change)

        product_ids = {
            item_form.cleaned_data["product"].pk
            for item_form in formset.forms
            if item_form.cleaned_data
            and not item_form.cleaned_data.get("DELETE", False)
            and item_form.cleaned_data.get("product") is not None
        }
        previous_prices = {}
        for product_id in product_ids:
            previous_item = (
                StockReceiptItem.objects
                .filter(
                    stock_receipt__depot=form.instance.depot,
                    product_id=product_id,
                )
                .order_by("-stock_receipt__receipt_date", "-created_at")
                .first()
            )
            previous_prices[product_id] = (
                previous_item.cost_price if previous_item else None
            )

        formset.save()
        record_depot_price_changes(
            form.instance, previous_prices, changed_by=request.user
        )


@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_date",
        "depot",
        "product",
        "transaction_type",
        "quantity",
        "unit_cost",
        "reference",
    )
    list_filter = ("depot", "transaction_type")
    search_fields = ("reference",)

    def has_change_permission(self, request, obj=None):
        # The ledger itself must never be hand-edited — it's the
        # audit trail. Adjustments go through a new ADJUSTMENT
        # transaction, not an edit to an existing row.
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(DepotPriceChange)
class DepotPriceChangeAdmin(admin.ModelAdmin):
    list_display = (
        "changed_at", "depot", "product", "previous_price",
        "new_price", "stock_receipt", "changed_by",
    )
    list_filter = ("depot", "changed_at")
    search_fields = ("product__sku", "product__name", "stock_receipt__invoice_number")
    readonly_fields = (
        "stock_receipt", "depot", "product", "previous_price",
        "new_price", "changed_at", "changed_by",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
