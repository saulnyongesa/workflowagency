from django.contrib import admin

from .models import Announcement, FAQ, PolicyPage, SupportTicket, SupportTicketReply


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "audience", "is_published", "starts_at", "ends_at")
    list_filter = ("audience", "is_published", "starts_at")
    search_fields = ("title", "message")
    readonly_fields = ("created_at", "updated_at", "created_by")

    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ("question", "category", "is_published", "sort_order")
    list_filter = ("category", "is_published")
    search_fields = ("question", "answer")


@admin.register(PolicyPage)
class PolicyPageAdmin(admin.ModelAdmin):
    list_display = ("title", "policy_type", "version", "is_published", "updated_at")
    list_filter = ("policy_type", "is_published")
    search_fields = ("title", "summary", "body")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at", "updated_at", "updated_by")

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


class SupportTicketReplyInline(admin.TabularInline):
    model = SupportTicketReply
    extra = 0
    readonly_fields = ("sender", "message", "is_staff_reply", "created_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "subject", "category", "priority", "status", "assigned_to")
    list_filter = ("status", "priority", "category", "created_at")
    search_fields = ("subject", "user__username", "user__email", "contact_email", "contact_phone")
    inlines = (SupportTicketReplyInline,)


@admin.register(SupportTicketReply)
class SupportTicketReplyAdmin(admin.ModelAdmin):
    list_display = ("created_at", "ticket", "sender", "is_staff_reply")
    list_filter = ("is_staff_reply", "created_at")
    search_fields = ("ticket__subject", "sender__username", "message")
    readonly_fields = ("ticket", "sender", "message", "is_staff_reply", "created_at")

    def has_add_permission(self, request):
        return False
