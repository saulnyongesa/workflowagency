from django.urls import path

from . import views

urlpatterns = [
    path("activate/", views.activation_page, name="activation_page"),
    path("deposit/", views.deposit_page, name="deposit_page"),
    path("transaction/<uuid:public_reference>/", views.transaction_detail, name="mpesa_transaction_detail"),
    path("callback/stk/", views.mpesa_stk_callback, name="mpesa_stk_callback"),
    path("callback/c2b/validation/", views.c2b_validation, name="mpesa_c2b_validation"),
    path("callback/c2b/confirmation/", views.c2b_confirmation, name="mpesa_c2b_confirmation"),
    path("admin/register-c2b/", views.register_c2b_urls_view, name="register_c2b_urls"),
]
