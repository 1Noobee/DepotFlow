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

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        role = getattr(user, "role", "") if user else ""

        # Commercial Managers can only assign a depot to their own
        # territory. This is enforced at form level as well as in views.
        if role == "TERRITORY_MANAGER":
            if getattr(user, "territory_id", None):
                self.fields["territory"].queryset = Territory.objects.filter(
                    pk=user.territory_id
                )
                self.fields["territory"].initial = user.territory_id
            else:
                self.fields["territory"].queryset = Territory.objects.none()
