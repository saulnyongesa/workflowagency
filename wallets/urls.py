from django.urls import path

from . import views

urlpatterns = [
    path("", views.wallet_dashboard, name="wallet_dashboard"),
    path("withdraw/", views.withdrawal_request_view, name="withdrawal_request"),
    path("withdrawals/<int:pk>/", views.withdrawal_detail, name="withdrawal_detail"),
    path("admin-adjustment/", views.admin_wallet_adjustment, name="admin_wallet_adjustment"),
    path("admin-withdrawals/", views.withdrawal_queue, name="withdrawal_queue"),
    path("admin-withdrawals/<int:pk>/approve/", views.approve_withdrawal_view, name="approve_withdrawal"),
    path("admin-withdrawals/<int:pk>/paid/", views.mark_withdrawal_paid_view, name="mark_withdrawal_paid"),
    path("admin-withdrawals/<int:pk>/reject/", views.reject_withdrawal_view, name="reject_withdrawal"),
]
