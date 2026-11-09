from django.urls import path

from fuel import views


urlpatterns = [
    path("api/admin/products/", views.ProductCreate.as_view()),
    path("api/admin/products/<int:pk>/", views.ProductUpdate.as_view()),
    path("api/admin/users/", views.UserCreate.as_view()),
    path("api/admin/users/<int:pk>/", views.UserUpdate.as_view()),
    path("api/purchases/", views.Purchases.as_view()),
]
