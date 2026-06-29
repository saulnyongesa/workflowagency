from django.contrib import admin
from django.utils.text import slugify

from .models import Job, JobCategory, JobClaim, JobSubmission
from .services import clone_job_as_new


@admin.register(JobCategory)
class JobCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "sort_order")
    list_filter = ("is_active",)
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "job_type",
        "content_format",
        "reward_amount",
        "worker_limit",
        "claims_count",
        "status",
        "review_mode",
    )
    list_filter = ("status", "job_type", "content_format", "category", "review_mode", "proof_type")
    search_fields = ("title", "description", "instructions", "content_body")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("claims_count", "approved_count", "pending_count", "rejected_count", "created_at", "updated_at")
    actions = ("publish_jobs", "pause_jobs", "clone_jobs")

    def save_model(self, request, obj, form, change):
        if not obj.slug:
            obj.slug = slugify(obj.title)
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="Publish selected jobs")
    def publish_jobs(self, request, queryset):
        queryset.update(status=Job.Status.PUBLISHED)

    @admin.action(description="Pause selected jobs")
    def pause_jobs(self, request, queryset):
        queryset.update(status=Job.Status.PAUSED)

    @admin.action(description="Clone selected jobs as drafts")
    def clone_jobs(self, request, queryset):
        for job in queryset:
            clone_job_as_new(job=job, created_by=request.user)


@admin.register(JobClaim)
class JobClaimAdmin(admin.ModelAdmin):
    list_display = ("claimed_at", "job", "user", "status", "expires_at", "submitted_at")
    list_filter = ("status", "claimed_at", "expires_at")
    search_fields = ("job__title", "user__username", "user__email")
    readonly_fields = ("job", "user", "status", "claimed_at", "expires_at", "submitted_at", "reviewed_at")

    def has_add_permission(self, request):
        return False


@admin.register(JobSubmission)
class JobSubmissionAdmin(admin.ModelAdmin):
    list_display = ("created_at", "claim", "user", "status", "reviewed_by", "reviewed_at")
    list_filter = ("status", "created_at", "reviewed_at")
    search_fields = ("claim__job__title", "user__username", "text_answer", "proof_url")
    readonly_fields = (
        "claim",
        "user",
        "text_answer",
        "proof_url",
        "proof_file",
        "metadata",
        "status",
        "ledger_transaction",
        "reviewed_by",
        "reviewed_at",
        "rejection_reason",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False
