from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from fuel.models import Product, Purchase, User


class JWTTests(APITestCase):
    def setUp(self):
        self.password = "BuyerSecret!12345"
        self.account = get_user_model().objects.create_user(
            username="buyer", password=self.password
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

    def sign_in(self, username="buyer", password=None):
        return self.client.post(
            "/api/token/",
            {
                "username": username,
                "password": password or self.password,
            },
            format="json",
        )

    def authorize(self, access):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

    def test_login_and_purchase(self):
        response = self.sign_in()
        self.assertEqual(response.status_code, 200)
        self.assertIn("refresh", response.data)
        self.authorize(response.data["access"])
        response = self.client.post(
            "/api/purchases/",
            {
                "product_id": self.product.pk,
                "litres": "10.00",
            },
            format="json",
            HTTP_X_USERNAME="someoneelse",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["remaining_balance"], "5000.00")
        self.assertEqual(Purchase.objects.get().user_id, self.profile.pk)
        self.assertEqual(len(self.client.get("/api/purchases/").data), 1)

    def test_invalid_credentials_and_tokens(self):
        self.assertEqual(self.sign_in(password="wrong").status_code, 401)
        self.assertEqual(self.client.get("/api/purchases/").status_code, 401)
        for token in ["invalid", str(RefreshToken.for_user(self.account))]:
            with self.subTest(token_type=token[:10]):
                self.authorize(token)
                self.assertEqual(self.client.get("/api/purchases/").status_code, 401)
        expired = AccessToken.for_user(self.account)
        expired.set_exp(
            from_time=timezone.now() - timedelta(minutes=10),
            lifetime=timedelta(minutes=1),
        )
        self.authorize(str(expired))
        self.assertEqual(self.client.get("/api/purchases/").status_code, 401)

    def test_refresh_rotates_and_prevents_reuse(self):
        original = self.sign_in().data["refresh"]
        response = self.client.post(
            "/api/token/refresh/", {"refresh": original}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.data["refresh"], original)
        self.authorize(response.data["access"])
        self.assertEqual(self.client.get("/api/purchases/").status_code, 200)
        self.assertEqual(
            self.client.post(
                "/api/token/refresh/",
                {
                    "refresh": original,
                },
                format="json",
            ).status_code,
            401,
        )

    def test_revoke_blocks_refresh(self):
        pair = self.sign_in().data
        self.assertEqual(
            self.client.post(
                "/api/token/revoke/",
                {
                    "refresh": pair["refresh"],
                },
                format="json",
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                "/api/token/refresh/",
                {
                    "refresh": pair["refresh"],
                },
                format="json",
            ).status_code,
            401,
        )
        self.authorize(pair["access"])
        self.assertEqual(self.client.get("/api/purchases/").status_code, 200)

    def test_password_change_invalidates_tokens(self):
        pair = self.sign_in().data
        self.account.set_password("ChangedSecret!12345")
        self.account.save()
        self.authorize(pair["access"])
        self.assertEqual(self.client.get("/api/purchases/").status_code, 401)
        self.assertEqual(
            self.client.post(
                "/api/token/refresh/",
                {
                    "refresh": pair["refresh"],
                },
                format="json",
            ).status_code,
            401,
        )

    def test_disabled_account_cannot_use_tokens(self):
        pair = self.sign_in().data
        self.account.is_active = False
        self.account.save()
        self.authorize(pair["access"])
        self.assertEqual(self.client.get("/api/purchases/").status_code, 401)
        self.assertEqual(
            self.client.post(
                "/api/token/refresh/",
                {
                    "refresh": pair["refresh"],
                },
                format="json",
            ).status_code,
            401,
        )

    def test_customer_cannot_manage_products_but_staff_can(self):
        self.authorize(self.sign_in().data["access"])
        payload = {
            "name": "Diesel",
            "price_per_litre": "400.00",
            "available_litres": "100.00",
        }
        self.assertEqual(
            self.client.post(
                "/api/admin/products/", payload, format="json"
            ).status_code,
            403,
        )
        get_user_model().objects.create_user(
            username="operator", password=self.password, is_staff=True
        )
        self.authorize(self.sign_in(username="operator").data["access"])
        self.assertEqual(
            self.client.post(
                "/api/admin/products/", payload, format="json"
            ).status_code,
            201,
        )

    def test_jwt_cannot_read_another_users_history(self):
        other = User.objects.create(
            username="other",
            first_name="Other",
            last_name="Buyer",
            birthdate="1990-01-01",
        )
        Purchase.objects.create(
            user=other, product=self.product, litres=1, total_price=500
        )
        self.authorize(self.sign_in().data["access"])
        self.assertEqual(
            self.client.get("/api/purchases/", HTTP_X_USERNAME="other").data, []
        )

    def test_expired_refresh_and_access_as_refresh_are_rejected(self):
        expired = RefreshToken.for_user(self.account)
        expired.set_exp(
            from_time=timezone.now() - timedelta(days=2), lifetime=timedelta(days=1)
        )
        for token in [str(expired), str(AccessToken.for_user(self.account)), "invalid"]:
            with self.subTest(token_type=token[:10]):
                self.assertEqual(
                    self.client.post(
                        "/api/token/refresh/",
                        {
                            "refresh": token,
                        },
                        format="json",
                    ).status_code,
                    401,
                )
