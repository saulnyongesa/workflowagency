from django.urls import path

from . import views

urlpatterns = [
    path("", views.referral_dashboard, name="referral_dashboard"),
]
