from rest_framework import viewsets

from core.permissions import role_permission
from .models import Territory, Depot
from .serializers import TerritorySerializer, DepotSerializer


class TerritoryViewSet(viewsets.ModelViewSet):
    queryset = Territory.objects.all().order_by("name")
    serializer_class = TerritorySerializer
    permission_classes = [role_permission("SUPER_ADMIN")]


class DepotViewSet(viewsets.ModelViewSet):
    queryset = Depot.objects.select_related("territory").order_by("name")
    serializer_class = DepotSerializer
    permission_classes = [role_permission("SUPER_ADMIN")]