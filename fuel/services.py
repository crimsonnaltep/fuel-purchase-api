from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from rest_framework.exceptions import NotFound, ValidationError

from .models import Product, Purchase, User


@transaction.atomic
def purchase_fuel(user_id, product_id, litres):
    user = User.objects.get(pk=user_id)
    try:
        product = Product.objects.get(pk=product_id)
    except Product.DoesNotExist:
        raise NotFound({"error": "Product not found."})

    if litres <= 0:
        raise ValidationError({"error": "Litres must be greater than zero."})
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
    return purchase, user.account_balance, product.available_litres
