from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone

from .models import Product, User


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "price_per_litre", "available_litres"]
        labels = {
            "name": "Name",
            "price_per_litre": "Price per litre",
            "available_litres": "Available litres",
        }


class UserForm(forms.ModelForm):
    password = forms.CharField(
        label="Login password",
        widget=forms.PasswordInput,
        required=False,
        help_text="Leave blank to keep the password of an existing account.",
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "birthdate", "account_balance"]
        labels = {
            "username": "Username",
            "first_name": "First name",
            "last_name": "Last name",
            "birthdate": "Birthdate",
            "account_balance": "Balance",
        }
        widgets = {
            "birthdate": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})
        }

    def clean_birthdate(self):
        value = self.cleaned_data["birthdate"]
        if value > timezone.localdate():
            raise forms.ValidationError("Birthdate cannot be in the future.")
        return value

    def clean(self):
        data = super().clean()
        username = data.get("username")
        accounts = get_user_model().objects.filter(username=username)
        if self.instance.account_id:
            accounts = accounts.exclude(pk=self.instance.account_id)
        if accounts.exists():
            self.add_error("username", "This username is already taken.")
        password = data.get("password")
        if not self.instance.account_id and not password:
            self.add_error("password", "Set a password for the new account.")
        if password:
            account = get_user_model()(
                username=username or "",
                first_name=data.get("first_name", ""),
                last_name=data.get("last_name", ""),
            )
            try:
                validate_password(password, account)
            except forms.ValidationError as error:
                self.add_error("password", error)
        return data

    @transaction.atomic
    def save(self, commit=True):
        profile = super().save(commit=False)
        account = profile.account if profile.account_id else get_user_model()()
        account.username = profile.username
        account.first_name = profile.first_name
        account.last_name = profile.last_name
        if self.cleaned_data["password"]:
            account.set_password(self.cleaned_data["password"])
        account.save()
        profile.account = account
        profile.save()
        return profile


class PurchaseForm(forms.Form):
    product_id = forms.IntegerField(widget=forms.HiddenInput, min_value=1)
    litres = forms.DecimalField(
        label="Quantity in litres",
        min_value=Decimal("0.01"),
        max_digits=12,
        decimal_places=2,
        initial=Decimal("10.00"),
        widget=forms.NumberInput(attrs={"step": "0.01"}),
    )
