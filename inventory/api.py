from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import role_permission
from .models import Product, Supplier, Promotion
from .serializers import (
    ProductSerializer, PriceHistorySerializer, PriceChangeSerializer,
    SupplierSerializer, PromotionSerializer,
)
from .services import record_price_change


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by("name")
    serializer_class = ProductSerializer
    permission_classes = [role_permission("SUPER_ADMIN", "DEPOT_MANAGER", "DEPOT_OFFICER")]

    @action(detail=True, methods=["get"])
    def price_history(self, request, pk=None):
        product = self.get_object()
        history = product.price_history.all()[:50]
        return Response(PriceHistorySerializer(history, many=True).data)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[role_permission("SUPER_ADMIN", "DEPOT_MANAGER")],
    )
    def change_price(self, request, pk=None):
        product = self.get_object()
        serializer = PriceChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        price_history = record_price_change(
            product,
            selling_price=serializer.validated_data["selling_price"],
            cost_price=serializer.validated_data.get("cost_price"),
            user=request.user,
            reason=serializer.validated_data.get("reason", ""),
        )

        return Response(PriceHistorySerializer(price_history).data, status=201)


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all().order_by("name")
    serializer_class = SupplierSerializer
    permission_classes = [role_permission("SUPER_ADMIN", "DEPOT_MANAGER", "DEPOT_OFFICER")]


class PromotionViewSet(viewsets.ModelViewSet):
    queryset = Promotion.objects.all().order_by("-start_date")
    serializer_class = PromotionSerializer
    permission_classes = [role_permission("SUPER_ADMIN", "DEPOT_MANAGER")]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)