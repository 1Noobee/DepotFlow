from django import forms
from django.forms import inlineformset_factory

from core.scoping import get_visible_depots
from .models import Product, Supplier, StockReceipt, StockReceiptItem, Promotion


class ProductForm(forms.ModelForm):
    """
    base_cost_price/base_selling_price are deliberately excluded —
    they're a display-only cache. Use PriceChangeForm (which goes
    through inventory.services.record_price_change) to actually
    change pricing.
    """

    class Meta:
        model = Product
        fields = [
            "sku", "name", "category", "package_type",
            "volume", "pack_size", "is_active",
        ]


class PriceChangeForm(forms.Form):
    """
    Not a ModelForm — PriceHistory is append-only and must always
    be created through inventory.services.record_price_change(),
    never edited directly.
    """

    selling_price = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    cost_price = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False,
                                     help_text="Optional informational reference; leave blank to keep the current reference.")
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "contact_person", "phone", "email", "address", "is_active"]


class StockReceiptForm(forms.ModelForm):
    """
    invoice_number is excluded — auto-generated in StockReceipt.save().
    """

    class Meta:
        model = StockReceipt
        fields = ["supplier", "depot", "receipt_date"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["depot"].queryset = get_visible_depots(user)


StockReceiptItemFormSet = inlineformset_factory(
    StockReceipt,
    StockReceiptItem,
    fields=["product", "quantity", "cost_price", "supplier_discount", "supplier_rebate"],
    extra=1,
    can_delete=True,
)


class PromotionForm(forms.ModelForm):
    class Meta:
        model = Promotion
        fields = [
            "name", "level", "promotion_type", "description", "products",
            "supplier", "depot", "start_date", "end_date",
            "percentage_value", "fixed_value", "buy_quantity", "get_quantity",
            "minimum_quantity", "maximum_quantity", "is_active",
        ]
        widgets = {
            "products": forms.SelectMultiple(attrs={"size": 8}),
        }