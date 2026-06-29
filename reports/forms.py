from django import forms
from django.contrib.auth import get_user_model

from core.models import FinanceSettings
from jobs.models import Job, JobCategory
from products.models import Product, ProductCategory
from support.models import Announcement, FAQ, PolicyPage


User = get_user_model()


class AdminFormMixin:
    def apply_styles(self):
        for field in self.fields.values():
            css_class = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            if isinstance(field.widget, forms.CheckboxInput):
                css_class = "form-check-input"
            field.widget.attrs["class"] = css_class


class FinanceSettingsForm(AdminFormMixin, forms.ModelForm):
    class Meta:
        model = FinanceSettings
        fields = (
            "activation_fee",
            "activation_credit_mode",
            "activation_withdrawable_amount",
            "referral_bonus_type",
            "referral_bonus_amount",
            "referral_bonus_percent",
            "referral_bonus_release_delay_hours",
            "minimum_withdrawal_amount",
            "maximum_daily_withdrawal_per_user",
            "withdrawal_fee_fixed",
            "withdrawal_fee_percent",
            "reserve_ratio_target",
            "minimum_platform_cash_buffer",
            "job_reward_release_delay_hours",
            "job_claims_enabled",
            "auto_approve_small_jobs",
            "auto_approve_job_reward_limit",
            "max_claims_per_user_per_day",
            "max_ad_watch_rewards_per_day",
            "deposit_enabled",
            "payout_enabled",
            "maintenance_mode",
        )
        help_texts = {
            "activation_fee": "Amount a new member pays to unlock the account. Manual activations also record this amount as confirmed cash.",
            "activation_credit_mode": "Controls where the activation value appears in the user's wallet after successful activation.",
            "activation_withdrawable_amount": "For mixed mode only, this is the part of the activation fee that becomes available balance.",
            "referral_bonus_type": "Choose whether referral rewards are fixed or calculated as a percentage of the activation fee.",
            "referral_bonus_amount": "Fixed referral reward amount when fixed referral bonuses are enabled.",
            "referral_bonus_percent": "Referral reward percentage when percentage referral bonuses are enabled.",
            "referral_bonus_release_delay_hours": "How long a referral bonus stays pending before it can be released.",
            "minimum_withdrawal_amount": "Smallest wallet amount a user can request for M-Pesa withdrawal.",
            "maximum_daily_withdrawal_per_user": "Total amount one user can request in a single day.",
            "withdrawal_fee_fixed": "Fixed fee deducted during withdrawal processing.",
            "withdrawal_fee_percent": "Percentage fee deducted during withdrawal processing.",
            "reserve_ratio_target": "Cash coverage target for wallet liabilities. Keep this at 1.00 or above.",
            "minimum_platform_cash_buffer": "Extra cash buffer kept aside before payouts are considered safe.",
            "job_reward_release_delay_hours": "Delay before job rewards become releasable when that flow is used.",
            "job_claims_enabled": "Turns job claiming on or off for all users without changing individual job statuses.",
            "auto_approve_small_jobs": "When enabled, low-value jobs can be approved automatically after proof is submitted.",
            "auto_approve_job_reward_limit": "Maximum reward amount that qualifies for auto approval.",
            "max_claims_per_user_per_day": "Limits how many jobs a user can claim per day.",
            "max_ad_watch_rewards_per_day": "Limits paid ad-watch claims per user per day.",
            "deposit_enabled": "Turns user deposits on or off.",
            "payout_enabled": "Turns withdrawal requests on or off.",
            "maintenance_mode": "Use this to pause sensitive money flows during maintenance.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()


class JobCategoryForm(AdminFormMixin, forms.ModelForm):
    class Meta:
        model = JobCategory
        fields = ("name", "slug", "icon", "color", "is_active", "sort_order")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()


class JobManageForm(AdminFormMixin, forms.ModelForm):
    class Meta:
        model = Job
        fields = (
            "category",
            "title",
            "slug",
            "job_type",
            "content_format",
            "description",
            "instructions",
            "content_body",
            "banner_image",
            "content_file",
            "content_url",
            "estimated_minutes",
            "reward_amount",
            "worker_limit",
            "status",
            "review_mode",
            "proof_type",
            "starts_at",
            "ends_at",
            "claim_expires_after_minutes",
            "max_claims_per_user",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "instructions": forms.Textarea(attrs={"rows": 5}),
            "content_body": forms.Textarea(attrs={"rows": 5}),
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }
        help_texts = {
            "content_format": "Select the content type users will complete, such as survey, story/article, video, file, or external link.",
            "content_body": "Paste article/story text, survey context, or video instructions that should appear on the job page.",
            "banner_image": "Optional banner shown on the job detail page. Use a clear landscape image.",
            "content_file": "Optional upload for files users need before submitting proof.",
            "content_url": "Optional external survey, video, article, game, or website URL.",
            "estimated_minutes": "Approximate time needed to complete the task.",
            "worker_limit": "When claims reach this number, the job is marked full automatically.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = JobCategory.objects.order_by("name")
        self.apply_styles()


class ProductCategoryForm(AdminFormMixin, forms.ModelForm):
    class Meta:
        model = ProductCategory
        fields = ("name", "slug", "description", "is_active", "sort_order")
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()


class ProductManageForm(AdminFormMixin, forms.ModelForm):
    class Meta:
        model = Product
        fields = (
            "category",
            "title",
            "slug",
            "product_type",
            "content_format",
            "status",
            "summary",
            "description",
            "price",
            "cover_image",
            "download_file",
            "external_url",
            "stock_quantity",
            "commission_type",
            "commission_amount",
            "commission_percent",
            "commission_release_delay_hours",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
        }
        help_texts = {
            "content_format": "Label the product content as a story, article, video, guide, template, file, link, or service.",
            "cover_image": "Required for a polished listing. If empty, users will see a placeholder banner.",
            "download_file": "Upload digital stories, videos, articles, guides, or files for direct delivery.",
            "external_url": "Use this when the product is delivered through a link instead of a file.",
            "stock_quantity": "Leave empty for unlimited stock.",
            "commission_type": "Controls whether referrers can earn from this product.",
            "commission_release_delay_hours": "How long product commissions stay pending before release.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = ProductCategory.objects.order_by("name")
        self.apply_styles()


class AnnouncementManageForm(AdminFormMixin, forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ("title", "message", "audience", "is_published", "starts_at", "ends_at")
        widgets = {
            "message": forms.Textarea(attrs={"rows": 4}),
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()


class FAQManageForm(AdminFormMixin, forms.ModelForm):
    class Meta:
        model = FAQ
        fields = ("category", "question", "answer", "is_published", "sort_order")
        widgets = {"answer": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()


class PolicyPageManageForm(AdminFormMixin, forms.ModelForm):
    class Meta:
        model = PolicyPage
        fields = ("title", "slug", "policy_type", "summary", "body", "version", "is_published")
        widgets = {
            "body": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_styles()


class ManualActivationForm(AdminFormMixin, forms.Form):
    user = forms.ModelChoiceField(
        queryset=User.objects.none(),
        label="User account",
        help_text="Only locked, non-staff accounts with a referral can be activated here.",
    )
    confirm_cash_received = forms.BooleanField(
        label="I confirm the activation fee has been received and deposited into platform cash.",
        help_text="This creates a successful activation record, credits the user's wallet, and posts any referral bonus.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user"].queryset = (
            User.objects.filter(is_staff=False, referred_by__isnull=False)
            .exclude(activation_status=User.ActivationStatus.ACTIVATED)
            .order_by("-date_joined")
        )
        self.apply_styles()

    def clean_user(self):
        user = self.cleaned_data["user"]
        if user.activation_status == User.ActivationStatus.ACTIVATED:
            raise forms.ValidationError("This account is already activated.")
        if not user.referred_by_id:
            raise forms.ValidationError("The user must add a referral code before activation.")
        return user
