from django import forms
from django.forms import inlineformset_factory

from .models import (
    Vehicle, VehicleSalesman, VehicleLoad, VehicleLoadItem,
    VehicleReturn, VehicleReturnItem,
)


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ["depot", "registration_number", "vehicle_name", "capacity", "is_active"]


class VehicleSalesmanForm(forms.ModelForm):
    class Meta:
        model = VehicleSalesman
        fields = ["name", "employee_id", "phone", "depot", "vehicle", "is_active"]


class VehicleLoadForm(forms.ModelForm):
    class Meta:
        model = VehicleLoad
        fields = ["salesman", "vehicle", "depot", "load_number", "load_date", "notes"]


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
    """

    class Meta:
        model = VehicleReturn
        fields = ["return_number", "return_date", "notes"]

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