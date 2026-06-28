from django.contrib import admin

from .models import LedgerTransaction, Wallet, WithdrawalRequest


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "available_balance",
        "pending_balance",
        "locked_balance",
        "total_earned",
        "total_withdrawn",
        "updated_at",
    )
    search_fields = ("user__username", "user__email", "user__phone_number")
    readonly_fields = (
        "user",
        "available_balance",
        "pending_balance",
        "locked_balance",
        "total_earned",
        "total_withdrawn",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False


@admin.register(LedgerTransaction)
class LedgerTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "user",
        "transaction_type",
        "direction",
        "balance_bucket",
        "amount",
        "status",
    )
    list_filter = ("transaction_type", "direction", "balance_bucket", "status", "created_at")
    search_fields = (
        "user__username",
        "user__email",
        "description",
        "idempotency_key",
        "public_reference",
    )
    readonly_fields = (
        "public_reference",
        "wallet",
        "user",
        "transaction_type",
        "direction",
        "balance_bucket",
        "amount",
        "status",
        "description",
        "idempotency_key",
        "source_app",
        "source_model",
        "source_id",
        "metadata",
        "created_by",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "amount", "fee", "net_amount", "phone_number", "status")
    list_filter = ("status", "created_at", "reviewed_at", "paid_at")
    search_fields = ("user__username", "user__email", "phone_number", "payout_reference")
    readonly_fields = (
        "user",
        "amount",
        "fee",
        "net_amount",
        "phone_number",
        "status",
        "request_debit_ledger",
        "lock_credit_ledger",
        "paid_ledger",
        "release_locked_ledger",
        "release_available_ledger",
        "reviewed_by",
        "reviewed_at",
        "paid_at",
        "rejection_reason",
        "payout_reference",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False
