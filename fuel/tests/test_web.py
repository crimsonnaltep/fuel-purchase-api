from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from fuel.models import Product, Purchase, User


class WebTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="operator", password="TestSecret!12345", is_staff=True
        )
        self.account = get_user_model().objects.create_user(
            username="buyer", password="TestSecret!12345"
        )
        self.profile = User.objects.create(
            account=self.account,
            username="buyer",
            first_name="Test",
            last_name="Buyer",
            birthdate="1995-01-01",
            account_balance="10000.00",
        )
        self.product = Product.objects.create(
            name="Petrol 95", price_per_litre="500.00", available_litres="1000.00"
        )

    def test_login_and_pages(self):
        self.assertEqual(self.client.get("/").status_code, 302)
        self.assertContains(self.client.get("/login/"), "Fuel Desk")
        response = self.client.post(
            "/login/", {"username": "operator", "password": "wrong"}
        )
        self.assertContains(response, "Sign-in failed")
        self.assertEqual(
            self.client.post(
                "/login/", {"username": "operator", "password": "TestSecret!12345"}
            ).status_code,
            302,
        )
        for path in [
            "/",
            "/products/",
            "/users/",
            "/purchases/",
            "/users/new/",
            "/products/new/",
            f"/users/{self.profile.pk}/edit/",
            f"/products/{self.product.pk}/edit/",
        ]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(self.client.get("/logout/").status_code, 405)
        self.assertEqual(self.client.post("/logout/").status_code, 302)
        self.assertEqual(self.client.get("/").status_code, 302)

    def test_staff_creates_login_and_updates_password(self):
        self.client.force_login(self.staff)
        data = {
            "username": "newbuyer",
            "password": "AnotherSecret!12345",
            "first_name": "New",
            "last_name": "Buyer",
            "birthdate": "2000-01-01",
            "account_balance": "100.25",
        }
        self.assertEqual(self.client.post("/users/new/", data).status_code, 302)
        profile = User.objects.get(username="newbuyer")
        self.assertTrue(profile.account.check_password(data["password"]))
        data.update(username="renamed", password="", account_balance="200.25")
        self.assertEqual(
            self.client.post(f"/users/{profile.pk}/edit/", data).status_code, 302
        )
        self.assertTrue(
            self.client.login(username="renamed", password="AnotherSecret!12345")
        )
        self.assertContains(self.client.get("/"), "200.25")

    def test_regular_user_cannot_manage_accounts_or_stock(self):
        self.client.force_login(self.account)
        for path in [
            "/users/",
            "/users/new/",
            f"/users/{self.profile.pk}/edit/",
            "/products/new/",
            f"/products/{self.product.pk}/edit/",
        ]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 403)
                self.assertEqual(self.client.post(path, {}).status_code, 403)

    def test_buy_and_insufficient_funds(self):
        self.client.force_login(self.account)
        path = f"/products/{self.product.pk}/buy/"
        self.assertContains(self.client.get(path), "10000.00")
        data = {"product_id": self.product.pk, "litres": "10.00"}
        self.assertEqual(self.client.post(path, data).status_code, 302)
        self.profile.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.profile.account_balance, Decimal("5000.00"))
        self.assertEqual(self.product.available_litres, Decimal("990.00"))
        response = self.client.post(path, {**data, "litres": "11.00"})
        self.assertContains(response, "Insufficient balance")
        self.assertEqual(Purchase.objects.count(), 1)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.account_balance, Decimal("5000.00"))
        self.assertContains(self.client.get("/purchases/"), "Petrol 95")

    def test_history_is_private(self):
        other = User.objects.create(
            username="other",
            first_name="Other",
            last_name="Buyer",
            birthdate="2000-01-01",
        )
        Purchase.objects.create(
            user=other, product=self.product, litres=1, total_price=500
        )
        self.client.force_login(self.account)
        self.assertNotContains(self.client.get("/purchases/"), "Petrol 95")
        self.client.force_login(self.staff)
        self.assertContains(self.client.get("/purchases/"), "Petrol 95")

    def test_csrf_protects_forms_and_api(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post("/login/", {}).status_code, 403)
        client.get("/login/")
        token = client.cookies["csrftoken"].value
        self.assertEqual(
            client.post(
                "/login/",
                {
                    "username": "buyer",
                    "password": "TestSecret!12345",
                    "csrfmiddlewaretoken": token,
                },
            ).status_code,
            302,
        )
        self.assertEqual(
            client.post(
                "/api/purchases/", {"product_id": self.product.pk, "litres": 1}
            ).status_code,
            403,
        )
        token = client.cookies["csrftoken"].value
        self.assertEqual(
            client.post(
                "/api/purchases/",
                {"product_id": self.product.pk, "litres": 1},
                HTTP_X_CSRFTOKEN=token,
            ).status_code,
            201,
        )

    def test_failed_write_rolls_back_purchase(self):
        self.client.force_login(self.account)
        with patch(
            "fuel.services.Purchase.objects.create",
            side_effect=RuntimeError("Write failed"),
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    f"/products/{self.product.pk}/buy/",
                    {
                        "product_id": self.product.pk,
                        "litres": "10",
                    },
                )
        self.profile.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.profile.account_balance, Decimal("10000.00"))
        self.assertEqual(self.product.available_litres, Decimal("1000.00"))
        self.assertFalse(Purchase.objects.exists())
