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


class SalesTargetForm(forms.ModelForm):
    class Meta:
        model = SalesTarget
        fields = ["salesman", "year", "month", "target_quantity"]


class VehicleLoadForm(forms.ModelForm):
    """
    load_number is excluded — auto-generated in VehicleLoad.save().
    """

    class Meta:
        model = VehicleLoad
        fields = ["salesman", "vehicle", "depot", "load_date", "notes"]


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