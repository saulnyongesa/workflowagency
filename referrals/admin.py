from django.contrib import admin

from .models import ReferralBonus


@admin.register(ReferralBonus)
class ReferralBonusAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "referrer",
        "referred_user",
        "amount",
        "status",
        "release_at",
        "credited_at",
    )
    list_filter = ("status", "created_at", "release_at")
    search_fields = ("referrer__username", "referred_user__username")
    readonly_fields = (
        "referrer",
        "referred_user",
        "activation_transaction",
        "ledger_transaction",
        "amount",
        "status",
        "release_at",
        "credited_at",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False
