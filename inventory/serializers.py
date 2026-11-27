from rest_framework import serializers

from .models import Product, Supplier, Promotion
from .services import get_current_selling_price


class ProductSerializer(serializers.ModelSerializer):
    # The one price: the price on the latest stock receipt for this product
    # (at any depot, since the API lists products across depots).
    current_price = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id", "sku", "name", "category", "package_type", "volume",
            "pack_size", "is_active", "current_price",
        ]
        read_only_fields = ["current_price"]

    def get_current_price(self, obj):
        return get_current_selling_price(obj)


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ["id", "name", "contact_person", "phone", "email", "address", "is_active"]


class PromotionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Promotion
        fields = [
            "id", "name", "level", "promotion_type", "description", "products",
            "supplier", "depot", "start_date", "end_date", "percentage_value",
            "fixed_value", "buy_quantity", "get_quantity", "minimum_quantity",
            "maximum_quantity", "is_active", "created_by",
        ]
        read_only_fields = ["created_by"]