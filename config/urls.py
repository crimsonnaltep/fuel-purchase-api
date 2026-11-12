from django.urls import include, path

from rest_framework_simplejwt.views import TokenBlacklistView, TokenObtainPairView

from fuel import views
from fuel.authentication import RefreshView

urlpatterns = [
    path("", include("fuel.web_urls")),
    path("api/token/", TokenObtainPairView.as_view(), name="token"),
    path("api/token/refresh/", RefreshView.as_view(), name="token-refresh"),
    path("api/token/revoke/", TokenBlacklistView.as_view(), name="token-revoke"),
    path("api/admin/products/", views.ProductCreate.as_view()),
    path("api/admin/products/<int:pk>/", views.ProductUpdate.as_view()),
    path("api/admin/users/", views.UserCreate.as_view()),
    path("api/admin/users/<int:pk>/", views.UserUpdate.as_view()),
    path("api/purchases/", views.Purchases.as_view()),
]
