from rest_framework.permissions import BasePermission, SAFE_METHODS


def role_permission(*roles):
    """
    Build a DRF permission class: any authenticated user can read
    (safe methods), but only staff or users whose role is in the
    given list can write. Mirrors the _can_manage_*()-style checks
    already used throughout the Django views, so the API enforces
    the same rules rather than a separate, possibly inconsistent
    set of rules.
    """

    class _RolePermission(BasePermission):
        def has_permission(self, request, view):
            if not request.user or not request.user.is_authenticated:
                return False

            if request.method in SAFE_METHODS:
                return True

            return request.user.is_staff or getattr(request.user, "role", "") in roles

    return _RolePermission