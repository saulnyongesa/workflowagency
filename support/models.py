from django.conf import settings
from django.db import models
from django.utils import timezone


class Announcement(models.Model):
    class Audience(models.TextChoices):
        ALL = "all", "All users"
        ACTIVE = "active", "Active users"
        STAFF = "staff", "Staff only"

    title = models.CharField(max_length=160)
    message = models.TextField()
    audience = models.CharField(max_length=20, choices=Audience.choices, default=Audience.ALL)
    is_published = models.BooleanField(default=True)
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_announcements",
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-starts_at"]
        indexes = [
            models.Index(fields=["is_published", "audience"]),
            models.Index(fields=["starts_at", "ends_at"]),
        ]

    def __str__(self):
        return self.title

    @property
    def is_live(self):
        now = timezone.now()
        return self.is_published and self.starts_at <= now and (self.ends_at is None or self.ends_at >= now)


class FAQ(models.Model):
    category = models.CharField(max_length=80, default="General")
    question = models.CharField(max_length=220)
    answer = models.TextField()
    is_published = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "sort_order", "question"]
        indexes = [
            models.Index(fields=["is_published", "category"]),
        ]

    def __str__(self):
        return self.question


class PolicyPage(models.Model):
    class PolicyType(models.TextChoices):
        TERMS = "terms", "Terms of service"
        PRIVACY = "privacy", "Privacy policy"
        WITHDRAWAL = "withdrawal", "Withdrawal policy"
        JOB_REWARD = "job_reward", "Job reward policy"
        REFERRAL = "referral", "Referral policy"
        SUPPORT = "support", "Support policy"
        OTHER = "other", "Other"

    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True)
    policy_type = models.CharField(max_length=30, choices=PolicyType.choices, default=PolicyType.OTHER)
    summary = models.CharField(max_length=240, blank=True)
    body = models.TextField()
    version = models.CharField(max_length=40, default="1.0")
    is_published = models.BooleanField(default=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_policy_pages",
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["policy_type", "title"]
        indexes = [
            models.Index(fields=["is_published", "policy_type"]),
        ]

    def __str__(self):
        return self.title


class SupportTicket(models.Model):
    class Category(models.TextChoices):
        ACCOUNT = "account", "Account"
        PAYMENT = "payment", "Payment/M-Pesa"
        JOBS = "jobs", "Jobs"
        WITHDRAWAL = "withdrawal", "Withdrawal"
        PRODUCTS = "products", "Products"
        REFERRALS = "referrals", "Referrals"
        TECHNICAL = "technical", "Technical"
        OTHER = "other", "Other"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        WAITING_USER = "waiting_user", "Waiting for user"
        WAITING_STAFF = "waiting_staff", "Waiting for staff"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="support_tickets")
    subject = models.CharField(max_length=180)
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.OTHER)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.OPEN)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_support_tickets",
    )
    admin_notes = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["status", "priority"]),
            models.Index(fields=["category", "status"]),
        ]

    def __str__(self):
        return self.subject


class SupportTicketReply(models.Model):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name="replies")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="support_replies")
    message = models.TextField()
    is_staff_reply = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["ticket", "created_at"]),
        ]

    def __str__(self):
        return f"Reply on {self.ticket}"
