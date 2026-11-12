from django.urls import path

from . import web

urlpatterns = [
    path("", web.dashboard, name="dashboard"),
    path("login/", web.sign_in, name="login"),
    path("logout/", web.sign_out, name="logout"),
    path("products/", web.products, name="products"),
    path("products/new/", web.product_edit, name="product-new"),
    path("products/<int:pk>/edit/", web.product_edit, name="product-edit"),
    path("products/<int:pk>/buy/", web.buy, name="buy"),
    path("users/", web.users, name="users"),
    path("users/new/", web.user_edit, name="user-new"),
    path("users/<int:pk>/edit/", web.user_edit, name="user-edit"),
    path("purchases/", web.history, name="history"),
]
