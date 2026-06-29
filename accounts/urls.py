from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import LoginForm

urlpatterns = [
    path("register/", views.register, name="register"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            authentication_form=LoginForm,
            template_name="accounts/login.html",
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("complete-referral/", views.complete_referral, name="complete_referral"),
    path("profile/", views.profile, name="profile"),
    path("password/", views.password_change, name="password_change"),
]
