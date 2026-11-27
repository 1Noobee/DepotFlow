from django import forms
from django.forms import inlineformset_factory

from core.scoping import get_default_depot, get_visible_depots, is_unrestricted
from .models import Product, Supplier, StockReceipt, StockReceiptItem, Promotion


class ProductForm(forms.ModelForm):
    """
    There is no price field: the price of a product comes from the
    stock receipt lines.
    """

    class Meta:
        model = Product
        fields = [
            "sku", "name", "category", "package_type",
            "volume", "pack_size", "is_active",
        ]


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "contact_person", "phone", "email", "address", "is_active"]

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if name.casefold() != "nbc":
            raise forms.ValidationError("NBC is the only supplier for new operational records. Existing historical supplier records are retained.")
        return "NBC"


class StockReceiptForm(forms.ModelForm):
    """
    invoice_number is excluded — auto-generated in StockReceipt.save().
    """

    class Meta:
        model = StockReceipt
        fields = ["supplier", "depot", "receipt_date"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # NBC is the only supplier for new operational receipts. Other supplier
        # rows are retained for historical records and reporting.
        self.fields["supplier"].queryset = Supplier.objects.filter(name__iexact="NBC", is_active=True)
        if user is not None:
            self.fields["depot"].queryset = get_visible_depots(user)
            default_depot = get_default_depot(user)
            if default_depot is not None:
                self.fields["depot"].initial = default_depot.pk
                self.fields["depot"].widget = forms.HiddenInput()


class StockReceiptItemForm(forms.ModelForm):
    class Meta:
        model = StockReceiptItem
        fields = ["product", "quantity", "cost_price"]
        labels = {"cost_price": "Current selling price"}
        help_texts = {
            "cost_price": (
                "Enter the current price per case from the NBC invoice (VAT included). "
                "This becomes the depot's current selling price. If it differs from "
                "the previous price, DepotFlow updates the current price and records "
                "the change in the price history."
            )
        }


StockReceiptItemFormSet = inlineformset_factory(
    StockReceipt,
    StockReceiptItem,
    form=StockReceiptItemForm,
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

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is None:
            return

        self.fields["depot"].queryset = get_visible_depots(user)

        # A blank depot means a company-wide promotion. Only unrestricted
        # users may create/keep those; everyone else must pick (or is
        # auto-assigned) one of their own depots.
        if not is_unrestricted(user):
            self.fields["depot"].required = True
            self.fields["depot"].empty_label = None
            default_depot = get_default_depot(user)
            if default_depot is not None:
                self.fields["depot"].initial = default_depot.pk
                self.fields["depot"].widget = forms.HiddenInput()