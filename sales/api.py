from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import role_permission
from .models import Customer, Sale, SaleItem
from .serializers import CustomerSerializer, SaleSerializer, SaleItemSerializer

# Matches sales.views._can_manage_sales.
_SALES_ROLES = ("SUPER_ADMIN", "DEPOT_MANAGER", "DEPOT_OFFICER", "SALESMAN")


class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.select_related("depot").order_by("name")
    serializer_class = CustomerSerializer
    permission_classes = [role_permission(*_SALES_ROLES)]


class SaleViewSet(viewsets.ModelViewSet):
    queryset = (
        Sale.objects
        .select_related("vehicle_load", "salesman", "customer")
        .prefetch_related("items")
        .order_by("-sale_date", "-created_at")
    )
    serializer_class = SaleSerializer
    permission_classes = [role_permission(*_SALES_ROLES)]

    @action(detail=True, methods=["post"])
    def finalize(self, request, pk=None):
        sale = self.get_object()
        sale.finalize()
        return Response(SaleSerializer(sale).data)


class SaleItemViewSet(viewsets.ModelViewSet):
    """
    Add/remove line items on a not-yet-finalized sale. Filter by
    ?sale=<id>. Load-reconciliation (sold + returned <= loaded) and
    the finalized-sale lock live in SaleItem.clean()/save() and are
    surfaced as normal 400s by core.exceptions.api_exception_handler.
    """

    queryset = SaleItem.objects.select_related("sale", "product", "promotion").all()
    serializer_class = SaleItemSerializer
    permission_classes = [role_permission(*_SALES_ROLES)]

    def get_queryset(self):
        queryset = super().get_queryset()
        sale_id = self.request.query_params.get("sale")
        if sale_id:
            queryset = queryset.filter(sale_id=sale_id)
        return queryset
