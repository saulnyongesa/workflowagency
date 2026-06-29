from django.urls import path

from . import views

urlpatterns = [
    path("", views.product_list, name="product_list"),
    path("library/", views.product_library, name="product_library"),
    path("purchase/<int:purchase_id>/", views.product_purchase_detail, name="product_purchase_detail"),
    path("<slug:slug>/buy/", views.purchase_product_view, name="purchase_product"),
    path("<slug:slug>/", views.product_detail, name="product_detail"),
]
