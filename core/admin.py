from django.contrib import admin
from django.forms.models import model_to_dict

from .models import AuditLog, FinanceSettings, SiteSetting
from .services import create_audit_log


@admin.register(FinanceSettings)
class FinanceSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        (
            "Activation",
            {
                "fields": (
                    "activation_fee",
                    "activation_credit_mode",
                    "activation_withdrawable_amount",
                )
            },
        ),
        (
            "Referrals",
            {
                "fields": (
                    "referral_bonus_type",
                    "referral_bonus_amount",
                    "referral_bonus_percent",
                    "referral_bonus_release_delay_hours",
                )
            },
        ),
        (
            "Withdrawals and reserve",
            {
                "fields": (
                    "minimum_withdrawal_amount",
                    "maximum_daily_withdrawal_per_user",
                    "withdrawal_fee_fixed",
                    "withdrawal_fee_percent",
                    "reserve_ratio_target",
                    "minimum_platform_cash_buffer",
                )
            },
        ),
        (
            "Jobs",
            {
                "fields": (
                    "job_reward_release_delay_hours",
                    "job_claims_enabled",
                    "auto_approve_small_jobs",
                    "auto_approve_job_reward_limit",
                    "max_claims_per_user_per_day",
                    "max_ad_watch_rewards_per_day",
                )
            },
        ),
        (
            "Feature toggles",
            {"fields": ("deposit_enabled", "payout_enabled", "maintenance_mode")},
        ),
    )
    readonly_fields = ("created_at", "updated_at", "updated_by")

    def has_add_permission(self, request):
        return not FinanceSettings.objects.exists()

    def save_model(self, request, obj, form, change):
        before = {}
        if change:
            before_obj = FinanceSettings.objects.get(pk=obj.pk)
            before = model_to_dict(before_obj)
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
        after = model_to_dict(obj)
        changes = {}
        for field, new_value in after.items():
            if field == "updated_by":
                continue
            old_value = before.get(field)
            if str(old_value) != str(new_value):
                changes[field] = {"old": str(old_value), "new": str(new_value)}
        if changes:
            create_audit_log(
                action=AuditLog.Action.FINANCE_SETTING_CHANGED,
                actor=request.user,
                instance=obj,
                changes=changes,
                request=request,
            )


@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    list_display = ("key", "label", "group", "value_type", "is_sensitive", "updated_at")
    list_filter = ("group", "value_type", "is_sensitive")
    search_fields = ("key", "label", "description")
    readonly_fields = ("created_at", "updated_at", "updated_by")

    def save_model(self, request, obj, form, change):
        before = {}
        if change:
            before = model_to_dict(SiteSetting.objects.get(pk=obj.pk))
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
        action = AuditLog.Action.UPDATED if change else AuditLog.Action.CREATED
        after = model_to_dict(obj)
        changes = {}
        for field, new_value in after.items():
            if field == "updated_by":
                continue
            old_value = before.get(field)
            if not change or str(old_value) != str(new_value):
                changes[field] = {"old": str(old_value), "new": str(new_value)}
        create_audit_log(
            action=action,
            actor=request.user,
            instance=obj,
            changes=changes,
            request=request,
        )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "actor", "model_label", "object_repr")
    list_filter = ("action", "model_label", "created_at")
    search_fields = ("object_repr", "model_label", "object_id", "actor__username")
    readonly_fields = (
        "actor",
        "action",
        "model_label",
        "object_id",
        "object_repr",
        "changes",
        "metadata",
        "ip_address",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
