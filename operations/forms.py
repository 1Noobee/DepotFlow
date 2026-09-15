from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.forms import inlineformset_factory

from .models import (
    Vehicle, VehicleSalesman, VehicleLoad, VehicleLoadItem,
    VehicleReturn, VehicleReturnItem, SalesTarget,
)

User = get_user_model()


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ["depot", "registration_number", "vehicle_name", "capacity", "is_active"]


class VehicleSalesmanForm(forms.ModelForm):
    """
    Also creates the salesman's login account in the same step —
    username/password below aren't VehicleSalesman fields, they
    create a linked User (role=SALESMAN) via save().

    If this salesman already has a login (editing an existing one),
    the username/password fields are optional and left blank by
    default — submitting them blank leaves the existing login
    untouched. A legacy salesman with no login yet can still have
    one added by filling these in on an edit.
    """

    username = forms.CharField(
        max_length=150,
        required=False,
        help_text="This salesman will log in with this username.",
    )
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput,
        required=False,
    )
    password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput,
        required=False,
    )

    class Meta:
        model = VehicleSalesman
        fields = ["name", "employee_id", "phone", "depot", "vehicle", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._needs_login = not (self.instance.pk and self.instance.user_id)

        if self._needs_login:
            self.fields["username"].required = True
            self.fields["password1"].required = True
            self.fields["password2"].required = True

    def clean_username(self):
        username = self.cleaned_data.get("username")

        if username:
            existing = User.objects.filter(username=username)
            if self.instance.user_id:
                existing = existing.exclude(pk=self.instance.user_id)
            if existing.exists():
                raise forms.ValidationError("This username is already taken.")

        return username

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 or password2:
            if password1 != password2:
                self.add_error("password2", "Passwords do not match.")
            else:
                try:
                    validate_password(password1)
                except DjangoValidationError as exc:
                    self.add_error("password1", exc)

        return cleaned_data

    def save(self, commit=True):
        salesman = super().save(commit=commit)

        username = self.cleaned_data.get("username")
        password1 = self.cleaned_data.get("password1")

        if commit and username and password1:
            user = User.objects.create_user(
                username=username,
                password=password1,
                role=User.Role.SALESMAN,
                depot=salesman.depot,
                first_name=salesman.name,
            )
            salesman.user = user
            salesman.save(update_fields=["user"])

        return salesman


class LoadCloseForm(forms.Form):
    """
    Captures the day's result for every product on a load in one
    step — how many units were sold and how many were returned —
    built fresh from VehicleLoad.reconciliation_status() so the
    "remaining" figure always reflects what's actually still
    outstanding right now.

    Submitting this creates a single Sale (with one SaleItem per
    product sold, customer left blank — this flow doesn't track
    per-customer detail) and/or a single VehicleReturn (with one
    item per product returned), then closes the load. See
    operations.views.load_close.
    """

    def __init__(self, *args, load=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.load = load
        self._row_meta = []

        number_attrs = {"class": "w-20 rounded border border-stone-300 text-sm px-2 py-1"}
        select_attrs = {"class": "rounded border border-stone-300 text-sm px-2 py-1"}

        for row in load.reconciliation_status():
            product = row["product"]
            remaining = row["remaining"]

            sold_name = f"sold_{product.id}"
            returned_name = f"returned_{product.id}"
            condition_name = f"condition_{product.id}"

            self.fields[sold_name] = forms.IntegerField(
                min_value=0, initial=max(remaining, 0),
                widget=forms.NumberInput(attrs=number_attrs),
            )
            self.fields[returned_name] = forms.IntegerField(
                min_value=0, initial=0,
                widget=forms.NumberInput(attrs=number_attrs),
            )
            self.fields[condition_name] = forms.ChoiceField(
                choices=[("GOOD", "Good"), ("DAMAGED", "Damaged")],
                initial="GOOD", required=False,
                widget=forms.Select(attrs=select_attrs),
            )

            self._row_meta.append({
                "product": product,
                "loaded": row["loaded"],
                "remaining": remaining,
                "sold_name": sold_name,
                "returned_name": returned_name,
                "condition_name": condition_name,
            })

    @property
    def rows(self):
        """Bound fields for template rendering, one row per product."""
        return [
            {
                "product": meta["product"],
                "loaded": meta["loaded"],
                "remaining": meta["remaining"],
                "sold": self[meta["sold_name"]],
                "returned": self[meta["returned_name"]],
                "condition": self[meta["condition_name"]],
            }
            for meta in self._row_meta
        ]

    def clean(self):
        cleaned_data = super().clean()

        for meta in self._row_meta:
            sold = cleaned_data.get(meta["sold_name"])
            returned = cleaned_data.get(meta["returned_name"])

            if sold is None or returned is None:
                continue

            if sold + returned != meta["remaining"]:
                self.add_error(
                    meta["sold_name"],
                    f"Sold + returned must add up to {meta['remaining']} "
                    f"(what's still unaccounted for) — got {sold + returned}."
                )

        return cleaned_data

    def get_results(self):
        """Rows with any activity, as plain dicts — skips products left untouched (0 sold, 0 returned)."""
        results = []

        for meta in self._row_meta:
            sold = self.cleaned_data.get(meta["sold_name"], 0)
            returned = self.cleaned_data.get(meta["returned_name"], 0)
            condition = self.cleaned_data.get(meta["condition_name"]) or "GOOD"

            if sold or returned:
                results.append({
                    "product": meta["product"],
                    "sold": sold,
                    "returned": returned,
                    "condition": condition,
                })

        return results


class SalesTargetForm(forms.ModelForm):
    class Meta:
        model = SalesTarget
        fields = ["salesman", "year", "month", "target_quantity"]


class VehicleLoadForm(forms.ModelForm):
    """
    load_number is excluded — auto-generated in VehicleLoad.save().
    load_date is excluded too — always today (the model's default),
    never user-editable, so a load's date can't be backdated or
    forward-dated. This is also what makes the "same-day reload"
    rule in VehicleLoad.clean() reliable: every load a user creates
    is dated today, full stop.
    """

    class Meta:
        model = VehicleLoad
        fields = ["salesman", "vehicle", "depot", "notes"]


VehicleLoadItemFormSet = inlineformset_factory(
    VehicleLoad,
    VehicleLoadItem,
    fields=["product", "quantity", "promo_discount"],
    extra=1,
    can_delete=True,
)


class VehicleReturnForm(forms.ModelForm):
    """
    vehicle_load is deliberately excluded from the form fields — a
    return is always created from a specific load's detail page,
    not picked in the form. It's set here in __init__ (not in the
    view after the fact) so VehicleReturn.clean() can safely access
    self.vehicle_load during validation.

    return_number is excluded too — auto-generated in VehicleReturn.save().
    """

    class Meta:
        model = VehicleReturn
        fields = ["return_date", "notes"]

    def __init__(self, *args, vehicle_load=None, **kwargs):
        super().__init__(*args, **kwargs)
        if vehicle_load is not None:
            self.instance.vehicle_load = vehicle_load


VehicleReturnItemFormSet = inlineformset_factory(
    VehicleReturn,
    VehicleReturnItem,
    fields=["product", "quantity", "condition", "notes"],
    extra=1,
    can_delete=True,
)