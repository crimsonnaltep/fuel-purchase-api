from functools import wraps

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST
from rest_framework.exceptions import APIException

from .forms import ProductForm, PurchaseForm, UserForm
from .models import Product, Purchase, User
from .services import purchase_fuel


def staff_required(view):
    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapped


@require_http_methods(["GET", "POST"])
def sign_in(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = AuthenticationForm(
        request, data=request.POST if request.method == "POST" else None
    )
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect("dashboard")
    return render(request, "login.html", {"form": form, "title": "Sign in"})


@require_POST
def sign_out(request):
    logout(request)
    return redirect("login")


@login_required
def dashboard(request):
    profile = User.objects.filter(account=request.user).first()
    purchases = Purchase.objects.select_related("user", "product")
    if not request.user.is_staff:
        purchases = purchases.filter(user=profile) if profile else purchases.none()
    return render(
        request,
        "dashboard.html",
        {
            "title": "Overview",
            "profile": profile,
            "purchases": purchases[:6],
            "purchase_count": purchases.count(),
            "spent": purchases.aggregate(total=Sum("total_price"))["total"] or 0,
            "stock": Product.objects.aggregate(total=Sum("available_litres"))["total"]
            or 0,
            "user_count": User.objects.count() if request.user.is_staff else 0,
        },
    )


@login_required
def products(request):
    return render(
        request,
        "products.html",
        {
            "title": "Fuel",
            "products": Product.objects.order_by("name"),
        },
    )


@staff_required
@require_http_methods(["GET", "POST"])
@transaction.atomic
def product_edit(request, pk=None):
    product = get_object_or_404(Product, pk=pk) if pk else None
    form = ProductForm(
        request.POST if request.method == "POST" else None, instance=product
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Fuel saved.")
        return redirect("products")
    return render(
        request,
        "form.html",
        {
            "title": "Edit fuel" if pk else "Add fuel",
            "form": form,
            "back": "products",
        },
    )


@staff_required
def users(request):
    return render(
        request,
        "users.html",
        {
            "title": "Users",
            "users": User.objects.select_related("account").order_by("username"),
        },
    )


@staff_required
@require_http_methods(["GET", "POST"])
@transaction.atomic
def user_edit(request, pk=None):
    user = get_object_or_404(User, pk=pk) if pk else None
    form = UserForm(request.POST if request.method == "POST" else None, instance=user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "User saved.")
        return redirect("users")
    return render(
        request,
        "form.html",
        {
            "title": "Edit user" if pk else "Add user",
            "form": form,
            "back": "users",
        },
    )


@login_required
def history(request):
    purchases = Purchase.objects.select_related("user", "product")
    if not request.user.is_staff:
        purchases = purchases.filter(user__account=request.user)
    return render(
        request, "history.html", {"title": "Purchases", "purchases": purchases}
    )


@login_required
@require_http_methods(["GET", "POST"])
def buy(request, pk):
    profile = get_object_or_404(User, account=request.user)
    product = get_object_or_404(Product, pk=pk)
    form = PurchaseForm(
        request.POST if request.method == "POST" else None,
        initial={"product_id": product.pk},
    )
    if request.method == "POST" and form.is_valid():
        if form.cleaned_data["product_id"] != product.pk:
            form.add_error(None, "The selected product changed. Refresh the page.")
        else:
            try:
                purchase, balance, stock = purchase_fuel(
                    profile.pk, product.pk, form.cleaned_data["litres"]
                )
            except APIException as error:
                form.add_error(None, str(error.detail.get("error", error.detail)))
            else:
                messages.success(
                    request,
                    f"Purchase #{purchase.pk} completed. Charged {purchase.total_price:.2f}.",
                )
                return redirect("history")
    profile.refresh_from_db()
    product.refresh_from_db()
    return render(
        request,
        "buy.html",
        {
            "title": "Buy fuel",
            "form": form,
            "profile": profile,
            "product": product,
        },
    )
