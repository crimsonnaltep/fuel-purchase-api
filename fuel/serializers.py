from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from .models import Product, Purchase, User


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "name", "price_per_litre", "available_litres"]


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "first_name", "last_name", "username", "birthdate", "account_balance"]

    def validate_birthdate(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError("Birthdate cannot be in the future.")
        return value


class PurchaseInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1, max_value=2**63 - 1)
    litres = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))


class PurchaseSerializer(serializers.ModelSerializer):
    product = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = Purchase
        fields = ["id", "product", "litres", "total_price", "created_at"]
