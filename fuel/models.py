from decimal import Decimal

from django.core.validators import MinValueValidator, RegexValidator
from django.db import models


class Product(models.Model):
    name = models.CharField(max_length=120)
    price_per_litre = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )
    available_litres = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(price_per_litre__gte=0), name="product_price_nonnegative"),
            models.CheckConstraint(condition=models.Q(available_litres__gte=0), name="product_stock_nonnegative"),
        ]


class User(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    username = models.CharField(
        max_length=150,
        unique=True,
        validators=[RegexValidator(r"\A[a-zA-Z0-9]+\Z", "Use only Latin letters and digits.")],
    )
    birthdate = models.DateField()
    account_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(account_balance__gte=0), name="user_balance_nonnegative"),
        ]


class Admin(models.Model):
    username = models.CharField(max_length=150, unique=True)
    api_key_hash = models.CharField(max_length=255)


class Purchase(models.Model):
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="purchases")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    litres = models.DecimalField(max_digits=12, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(litres__gt=0), name="purchase_litres_positive"),
            models.CheckConstraint(condition=models.Q(total_price__gte=0), name="purchase_total_nonnegative"),
        ]
