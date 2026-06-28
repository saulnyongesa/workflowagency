from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        "username",
        "email",
        "phone_number",
        "status",
        "activation_status",
        "kyc_status",
        "is_staff",
    )
    list_filter = (
        "status",
        "activation_status",
        "kyc_status",
        "is_staff",
        "is_superuser",
        "is_active",
    )
    search_fields = ("username", "email", "phone_number", "referral_code")
    readonly_fields = ("date_joined", "last_login")
    fieldsets = UserAdmin.fieldsets + (
        (
            "Workflow Agency",
            {
                "fields": (
                    "phone_number",
                    "country",
                    "referral_code",
                    "referred_by",
                    "status",
                    "activation_status",
                    "kyc_status",
                    "phone_verified_at",
                )
            },
        ),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "Workflow Agency",
            {
                "fields": (
                    "email",
                    "phone_number",
                    "country",
                    "referred_by",
                )
            },
        ),
    )

# Register your models here.
