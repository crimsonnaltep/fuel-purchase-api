from django.contrib.auth.hashers import check_password
from django.db import transaction
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Admin, Product, Purchase, User
from .services import purchase_fuel
from .serializers import (
    ProductSerializer,
    PurchaseInputSerializer,
    PurchaseSerializer,
    UserSerializer,
)


class CanManageFuel(BasePermission):
    message = "Missing or invalid administrator API key."

    def has_permission(self, request, view):
        if request.user.is_authenticated and request.user.is_staff:
            return True
        key = request.headers.get("X-Admin-Key")
        if not key or len(key) > 128:
            raise PermissionDenied(self.message)
        hashes = Admin.objects.values_list("api_key_hash", flat=True)
        if not any(check_password(key, key_hash) for key_hash in hashes):
            raise PermissionDenied(self.message)
        return True


class AdminCreate(generics.CreateAPIView):
    permission_classes = [CanManageFuel]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class AdminUpdate(generics.UpdateAPIView):
    permission_classes = [CanManageFuel]
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
    permission_classes = [IsAuthenticated]

    def get_user(self, request):
        try:
            return User.objects.get(account=request.user)
        except User.DoesNotExist:
            raise NotFound({"error": "User profile not found."})

    def get(self, request):
        user = self.get_user(request)
        purchases = user.purchases.select_related("product")
        return Response(PurchaseSerializer(purchases, many=True).data)

    def post(self, request):
        user = self.get_user(request)
        serializer = PurchaseInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        purchase, balance, stock = purchase_fuel(
            user.pk,
            serializer.validated_data["product_id"],
            serializer.validated_data["litres"],
        )
        data = PurchaseSerializer(purchase).data
        data["remaining_balance"] = format(balance, ".2f")
        data["remaining_stock_litres"] = format(stock, ".2f")
        return Response(data, status=status.HTTP_201_CREATED)
