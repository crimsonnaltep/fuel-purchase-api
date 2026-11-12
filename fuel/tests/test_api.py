from decimal import Decimal
from io import StringIO

from django.contrib.auth.hashers import check_password
from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APITestCase

from fuel.models import Admin, Product, Purchase, User


class AdminAPITests(APITestCase):
    def setUp(self):
        output = StringIO()
        call_command("create_admin", "operator", stdout=output)
        self.key = output.getvalue().strip()
        self.headers = {"HTTP_X_ADMIN_KEY": self.key}
        self.product = {
            "name": "Petrol 95",
            "price_per_litre": "500.00",
            "available_litres": "1000.00",
        }
        self.user = {
            "username": "john",
            "first_name": "John",
            "last_name": "Smith",
            "birthdate": "1995-05-20",
        }

    def test_key_is_hashed_and_required(self):
        stored_hash = Admin.objects.get(username="operator").api_key_hash
        self.assertNotEqual(stored_hash, self.key)
        self.assertTrue(check_password(self.key, stored_hash))
        for headers in (
            {},
            {"HTTP_X_USERNAME": "john"},
            {"HTTP_X_ADMIN_KEY": "invalid"},
        ):
            with self.subTest(headers=headers):
                self.assertEqual(
                    self.client.post(
                        "/api/admin/products/", self.product, **headers
                    ).status_code,
                    403,
                )
                self.assertEqual(
                    self.client.patch("/api/admin/users/1/", {}, **headers).status_code,
                    403,
                )

    def test_create_and_update_product(self):
        url = "/api/admin/products/"
        response = self.client.post(url, self.product, **self.headers)
        self.assertEqual(response.status_code, 201)
        detail = f"{url}{response.data['id']}/"
        self.assertEqual(
            self.client.patch(
                detail, {"available_litres": "25.50"}, **self.headers
            ).status_code,
            200,
        )
        for field in ("available_litres", "price_per_litre"):
            with self.subTest(field=field):
                self.assertEqual(
                    self.client.patch(
                        detail, {field: "-0.01"}, **self.headers
                    ).status_code,
                    400,
                )
        self.assertEqual(Product.objects.get().available_litres, Decimal("25.50"))

    def test_create_and_update_user(self):
        url = "/api/admin/users/"
        response = self.client.post(url, self.user, **self.headers)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["account_balance"], "0.00")
        self.assertEqual(
            self.client.post(url, self.user, **self.headers).status_code, 400
        )
        self.assertEqual(
            self.client.post(
                url, {**self.user, "username": "тест"}, **self.headers
            ).status_code,
            400,
        )
        detail = f"{url}{response.data['id']}/"
        self.assertEqual(
            self.client.patch(
                detail, {"account_balance": "100.25"}, **self.headers
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.patch(
                detail, {"account_balance": "-0.01"}, **self.headers
            ).status_code,
            400,
        )
        self.assertEqual(User.objects.get().account_balance, Decimal("100.25"))


class PurchaseAPITests(APITestCase):
    url = "/api/purchases/"

    def setUp(self):
        self.user = User.objects.create(
            username="john",
            first_name="John",
            last_name="Smith",
            birthdate="1995-05-20",
            account_balance=Decimal("10000.00"),
        )
        account = get_user_model().objects.create_user(
            username="john", password="TestSecret!12345"
        )
        self.user.account = account
        self.user.save(update_fields=["account"])
        self.client.force_login(account)
        self.product = Product.objects.create(
            name="Petrol 95",
            price_per_litre=Decimal("500.00"),
            available_litres=Decimal("1000.00"),
        )

    def buy(self, litres, product_id=None):
        return self.client.post(
            self.url,
            {
                "product_id": product_id if product_id is not None else self.product.pk,
                "litres": litres,
            },
            format="json",
            HTTP_X_USERNAME=self.user.username,
        )

    def test_purchase_updates_stock_balance_and_history(self):
        response = self.buy("10.25")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["total_price"], "5125.00")
        self.assertEqual(response.data["remaining_balance"], "4875.00")
        self.assertEqual(response.data["remaining_stock_litres"], "989.75")
        self.user.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.user.account_balance, Decimal("4875.00"))
        self.assertEqual(self.product.available_litres, Decimal("989.75"))

        history = self.client.get(self.url, HTTP_X_USERNAME=self.user.username)
        self.assertEqual(history.status_code, 200)
        self.assertEqual(len(history.data), 1)
        self.assertEqual(history.data[0]["id"], response.data["id"])
        self.assertIn("created_at", history.data[0])

        User.objects.create(
            username="jane",
            first_name="Jane",
            last_name="Smith",
            birthdate="1995-05-20",
        )
        jane = get_user_model().objects.create_user(
            username="jane", password="TestSecret!12345"
        )
        User.objects.filter(username="jane").update(account=jane)
        self.client.force_login(jane)
        self.assertEqual(self.client.get(self.url, HTTP_X_USERNAME="john").data, [])

    def test_invalid_purchases_leave_database_unchanged(self):
        cases = [
            ("0", self.product.pk, 400, None),
            ("-1", self.product.pk, 400, None),
            ("bad", self.product.pk, 400, None),
            ("10", self.product.pk + 1, 404, "Product not found."),
            ("1001", self.product.pk, 400, "Not enough fuel available."),
            ("21", self.product.pk, 400, "Insufficient balance."),
        ]
        for litres, product_id, expected_status, error in cases:
            with self.subTest(litres=litres, product_id=product_id):
                response = self.buy(litres, product_id)
                self.assertEqual(response.status_code, expected_status)
                if error:
                    self.assertEqual(response.data["error"], error)
                self.user.refresh_from_db()
                self.product.refresh_from_db()
                self.assertEqual(self.user.account_balance, Decimal("10000.00"))
                self.assertEqual(self.product.available_litres, Decimal("1000.00"))
                self.assertFalse(Purchase.objects.exists())

    def test_session_is_required(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.assertEqual(
            self.client.get(self.url, HTTP_X_USERNAME="john").status_code, 401
        )
