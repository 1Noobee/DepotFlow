from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from core.permissions import role_permission
from core.scoping import is_unrestricted, user_can_access_depot
from .models import Product, Supplier, Promotion
from .serializers import ProductSerializer, SupplierSerializer, PromotionSerializer
from .scoping import visible_promotions, can_edit_promotion


class OwnerReadOnlyViewSet(viewsets.ModelViewSet):
    """Depot Owners can read inventory reference data, never mutate it."""
    def get_permissions(self):
        if getattr(self.request.user, "role", "") == "DEPOT_OWNER" and self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return super().get_permissions()


class ProductViewSet(OwnerReadOnlyViewSet):
    queryset = Product.objects.all().order_by("name")
    serializer_class = ProductSerializer
    permission_classes = [role_permission("SUPER_ADMIN", "DEPOT_MANAGER", "DEPOT_OFFICER")]


class SupplierViewSet(OwnerReadOnlyViewSet):
    queryset = Supplier.objects.all().order_by("name")
    serializer_class = SupplierSerializer
    permission_classes = [role_permission("SUPER_ADMIN", "DEPOT_MANAGER", "DEPOT_OFFICER")]


class PromotionViewSet(OwnerReadOnlyViewSet):
    """
    Scoped like the HTML screens: company-wide promotions (no depot) are
    visible to everyone but only unrestricted users may change them;
    depot-specific ones are visible/editable only within the user's own
    depots.
    """

    serializer_class = PromotionSerializer
    permission_classes = [role_permission("SUPER_ADMIN", "DEPOT_MANAGER")]

    def get_queryset(self):
        return visible_promotions(self.request.user).order_by("-start_date")

    def _check_depot_allowed(self, depot):
        user = self.request.user
        if is_unrestricted(user):
            return
        if depot is None or not user_can_access_depot(user, depot):
            raise PermissionDenied("You can only create or edit promotions for your own depot.")

    def perform_create(self, serializer):
        self._check_depot_allowed(serializer.validated_data.get("depot"))
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        if not can_edit_promotion(self.request.user, serializer.instance):
            raise PermissionDenied("You cannot edit this promotion.")
        self._check_depot_allowed(serializer.validated_data.get("depot", serializer.instance.depot))
        serializer.save()

    def perform_destroy(self, instance):
        if not can_edit_promotion(self.request.user, instance):
            raise PermissionDenied("You cannot delete this promotion.")
        instance.delete()