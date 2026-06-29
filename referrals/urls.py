from django.urls import path

from . import views

urlpatterns = [
    path("join/<str:code>/", views.join_with_referral, name="referral_join"),
    path("", views.referral_dashboard, name="referral_dashboard"),
]
