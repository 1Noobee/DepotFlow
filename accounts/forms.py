from django import forms
from .models import User


class ProfileForm(forms.ModelForm):
    """
    Self-service profile editing. Deliberately excludes role, depot,
    territory, is_active, is_staff, is_superuser — those are
    assigned by an administrator through Django admin only, so every
    permission-relevant change goes through one auditable path (see
    accounts.signals.log_user_permission_change).
    """

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone"]