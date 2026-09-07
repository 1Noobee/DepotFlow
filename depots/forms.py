from django import forms

from .models import Territory, Depot


class TerritoryForm(forms.ModelForm):
    class Meta:
        model = Territory
        fields = ["name"]


class DepotForm(forms.ModelForm):
    class Meta:
        model = Depot
        fields = ["territory", "name", "code", "address"]