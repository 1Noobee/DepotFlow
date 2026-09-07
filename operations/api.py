from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import role_permission
from .models import (
    Vehicle, VehicleSalesman, VehicleLoad, VehicleLoadItem,
    VehicleReturn, VehicleReturnItem,
)
from .serializers import (
    VehicleSerializer, VehicleSalesmanSerializer,
    VehicleLoadSerializer, VehicleLoadItemSerializer,
    VehicleReturnSerializer, VehicleReturnItemSerializer,
)

# Matches operations.views._can_manage_operations.
_OPERATIONS_ROLES = ("SUPER_ADMIN", "DEPOT_MANAGER", "DEPOT_OFFICER")


class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.select_related("depot").order_by("registration_number")
    serializer_class = VehicleSerializer
    permission_classes = [role_permission(*_OPERATIONS_ROLES)]


class VehicleSalesmanViewSet(viewsets.ModelViewSet):
    queryset = VehicleSalesman.objects.select_related("depot", "vehicle").order_by("name")
    serializer_class = VehicleSalesmanSerializer
    permission_classes = [role_permission(*_OPERATIONS_ROLES)]


class VehicleLoadViewSet(viewsets.ModelViewSet):
    queryset = (
        VehicleLoad.objects
        .select_related("depot", "vehicle", "salesman")
        .prefetch_related("items")
        .order_by("-load_date", "-created_at")
    )
    serializer_class = VehicleLoadSerializer
    permission_classes = [role_permission(*_OPERATIONS_ROLES)]

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        load = self.get_object()
        load.close_load()
        return Response(VehicleLoadSerializer(load).data)


class VehicleLoadItemViewSet(viewsets.ModelViewSet):
    """
    Add/remove line items on an open vehicle load.

    Filter by ?vehicle_load=<id>. Stock-availability and closed-load
    checks live in VehicleLoadItem.clean()/save() and are surfaced as
    normal 400s by core.exceptions.api_exception_handler — this
    viewset does not duplicate that logic.
    """

    queryset = VehicleLoadItem.objects.select_related("vehicle_load", "product").all()
    serializer_class = VehicleLoadItemSerializer
    permission_classes = [role_permission(*_OPERATIONS_ROLES)]

    def get_queryset(self):
        queryset = super().get_queryset()
        vehicle_load_id = self.request.query_params.get("vehicle_load")
        if vehicle_load_id:
            queryset = queryset.filter(vehicle_load_id=vehicle_load_id)
        return queryset


class VehicleReturnViewSet(viewsets.ModelViewSet):
    queryset = (
        VehicleReturn.objects
        .select_related("vehicle_load")
        .prefetch_related("items")
        .order_by("-return_date", "-created_at")
    )
    serializer_class = VehicleReturnSerializer
    permission_classes = [role_permission(*_OPERATIONS_ROLES)]

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        vehicle_return = self.get_object()
        vehicle_return.confirm_return()
        return Response(VehicleReturnSerializer(vehicle_return).data)


class VehicleReturnItemViewSet(viewsets.ModelViewSet):
    """Filter by ?vehicle_return=<id>."""

    queryset = VehicleReturnItem.objects.select_related("vehicle_return", "product").all()
    serializer_class = VehicleReturnItemSerializer
    permission_classes = [role_permission(*_OPERATIONS_ROLES)]

    def get_queryset(self):
        queryset = super().get_queryset()
        vehicle_return_id = self.request.query_params.get("vehicle_return")
        if vehicle_return_id:
            queryset = queryset.filter(vehicle_return_id=vehicle_return_id)
        return queryset
