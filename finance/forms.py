from django import forms

from core.scoping import get_default_depot, get_visible_depots
from .models import Expense, SupplierPayment, SupplierRebate


class ExpenseForm(forms.ModelForm):
    """
    reference_number is auto-generated in Expense.save(). approved/
    is_reversed/reversed_* are workflow/locked fields, never set at
    creation time through this form.
    """

    class Meta:
        model = Expense
        fields = ["depot", "category", "expense_date", "description", "amount", "payment_method"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["depot"].queryset = get_visible_depots(user)
            default_depot = get_default_depot(user)
            if default_depot is not None:
                self.fields["depot"].initial = default_depot.pk
                self.fields["depot"].widget = forms.HiddenInput()


class SupplierPaymentForm(forms.ModelForm):
    class Meta:
        model = SupplierPayment
        fields = ["depot", "supplier", "stock_receipt", "payment_date", "amount", "notes"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["depot"].queryset = get_visible_depots(user)
            default_depot = get_default_depot(user)
            if default_depot is not None:
                self.fields["depot"].initial = default_depot.pk
                self.fields["depot"].widget = forms.HiddenInput()


class SupplierRebateForm(forms.ModelForm):
    class Meta:
        model = SupplierRebate
        fields = ["depot", "supplier", "rebate_date", "amount", "description"]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["depot"].queryset = get_visible_depots(user)
            default_depot = get_default_depot(user)
            if default_depot is not None:
                self.fields["depot"].initial = default_depot.pk
                self.fields["depot"].widget = forms.HiddenInput()


class ReversalForm(forms.Form):
    """
    Not a ModelForm — reversal is always performed through
    LedgerPostedRecord.reverse(), never a direct field edit.
    """

    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=True,
        help_text="Required — explain why this record is being reversed.",
    )