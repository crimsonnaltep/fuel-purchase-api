from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth.hashers import check_password
from django.db import transaction
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Admin, Product, Purchase, User
from .serializers import ProductSerializer, PurchaseInputSerializer, PurchaseSerializer, UserSerializer


class HasAdminKey(BasePermission):
    message = "Missing or invalid administrator API key."

    def has_permission(self, request, view):
        key = request.headers.get("X-Admin-Key")
        if not key or len(key) > 128:
            return False
        hashes = Admin.objects.values_list("api_key_hash", flat=True)
        return any(check_password(key, key_hash) for key_hash in hashes)


class AdminCreate(generics.CreateAPIView):
    permission_classes = [HasAdminKey]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class AdminUpdate(generics.UpdateAPIView):
    permission_classes = [HasAdminKey]
    http_method_names = ["patch", "options"]

    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)


class ProductCreate(AdminCreate):
    serializer_class = ProductSerializer


class ProductUpdate(AdminUpdate):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer


class UserCreate(AdminCreate):
    serializer_class = UserSerializer


class UserUpdate(AdminUpdate):
    queryset = User.objects.all()
    serializer_class = UserSerializer


class Purchases(APIView):
    def get_user(self, request):
        username = request.headers.get("X-Username")
        if not username:
            raise ValidationError({"error": "X-Username header is required."})
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist:
            raise NotFound({"error": "User not found."})

    def get(self, request):
        user = self.get_user(request)
        purchases = user.purchases.select_related("product")
        return Response(PurchaseSerializer(purchases, many=True).data)

    @transaction.atomic
    def post(self, request):
        user = self.get_user(request)
        serializer = PurchaseInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        litres = serializer.validated_data["litres"]

        try:
            product = Product.objects.get(pk=serializer.validated_data["product_id"])
        except Product.DoesNotExist:
            raise NotFound({"error": "Product not found."})

        if litres > product.available_litres:
            raise ValidationError({"error": "Not enough fuel available."})

        total_price = (product.price_per_litre * litres).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        if total_price > user.account_balance:
            raise ValidationError({"error": "Insufficient balance."})

        user.account_balance -= total_price
        product.available_litres -= litres
        user.save(update_fields=["account_balance"])
        product.save(update_fields=["available_litres"])
        purchase = Purchase.objects.create(
            user=user, product=product, litres=litres, total_price=total_price
        )
        data = PurchaseSerializer(purchase).data
        data["remaining_balance"] = format(user.account_balance, ".2f")
        data["remaining_stock_litres"] = format(product.available_litres, ".2f")
        return Response(data, status=status.HTTP_201_CREATED)
