from django.contrib import admin

from .models import MpesaTransaction


@admin.register(MpesaTransaction)
class MpesaTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "user",
        "transaction_kind",
        "payment_method",
        "amount",
        "status",
        "mpesa_receipt_number",
    )
    list_filter = ("transaction_kind", "payment_method", "status", "created_at")
    search_fields = (
        "user__username",
        "user__email",
        "phone_number",
        "account_reference",
        "checkout_request_id",
        "mpesa_receipt_number",
    )
    readonly_fields = (
        "public_reference",
        "user",
        "transaction_kind",
        "payment_method",
        "status",
        "amount",
        "phone_number",
        "account_reference",
        "merchant_request_id",
        "checkout_request_id",
        "mpesa_receipt_number",
        "result_code",
        "result_description",
        "raw_request",
        "raw_callback",
        "confirmed_at",
        "processed_at",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False
