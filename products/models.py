import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone


class ProductCategory(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "product categories"

    def __str__(self):
        return self.name


class Product(models.Model):
    class ProductType(models.TextChoices):
        DIGITAL_FILE = "digital_file", "Digital file"
        EXTERNAL_LINK = "external_link", "External link"
        SERVICE = "service", "Service/manual delivery"

    class ContentFormat(models.TextChoices):
        GUIDE = "guide", "Guide"
        STORY = "story", "Story"
        ARTICLE = "article", "Article"
        VIDEO = "video", "Video"
        TEMPLATE = "template", "Template"
        FILE = "file", "File/resource"
        LINK = "link", "Link resource"
        SERVICE = "service", "Service"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        PAUSED = "paused", "Paused"
        ARCHIVED = "archived", "Archived"

    class CommissionType(models.TextChoices):
        NONE = "none", "No commission"
        FIXED = "fixed", "Fixed amount"
        PERCENT = "percent", "Percentage"

    category = models.ForeignKey(ProductCategory, on_delete=models.PROTECT, related_name="products")
    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True)
    product_type = models.CharField(max_length=30, choices=ProductType.choices, default=ProductType.DIGITAL_FILE)
    content_format = models.CharField(max_length=30, choices=ContentFormat.choices, default=ContentFormat.FILE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    summary = models.CharField(max_length=240)
    description = models.TextField()
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    cover_image = models.FileField(upload_to="products/covers/%Y/%m/", blank=True)
    download_file = models.FileField(upload_to="products/files/%Y/%m/", blank=True)
    external_url = models.URLField(blank=True)
    stock_quantity = models.PositiveIntegerField(null=True, blank=True)
    sold_count = models.PositiveIntegerField(default=0)
    commission_type = models.CharField(
        max_length=20,
        choices=CommissionType.choices,
        default=CommissionType.NONE,
    )
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    commission_release_delay_hours = models.PositiveIntegerField(default=24)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_products",
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "product_type"]),
            models.Index(fields=["category", "status"]),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(price__gte=0), name="product_price_non_negative"),
            models.CheckConstraint(condition=Q(commission_amount__gte=0), name="product_commission_amount_non_negative"),
            models.CheckConstraint(condition=Q(commission_percent__gte=0), name="product_commission_percent_non_negative"),
        ]

    def __str__(self):
        return self.title

    @property
    def is_in_stock(self):
        return self.stock_quantity is None or self.sold_count < self.stock_quantity

    @property
    def is_available(self):
        return self.status == self.Status.PUBLISHED and self.is_in_stock

    def get_absolute_url(self):
        return reverse("product_detail", kwargs={"slug": self.slug})

    def clean(self):
        if self.commission_percent < 0 or self.commission_percent > 100:
            raise ValidationError({"commission_percent": "Percent must be between 0 and 100."})
        if self.product_type == self.ProductType.EXTERNAL_LINK and not self.external_url:
            raise ValidationError({"external_url": "External link products need a delivery URL."})
        if self.product_type == self.ProductType.DIGITAL_FILE and not self.download_file and self.status == self.Status.PUBLISHED:
            raise ValidationError({"download_file": "Published digital file products need a downloadable file."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class ProductPurchase(models.Model):
    class Status(models.TextChoices):
        COMPLETED = "completed", "Completed"
        REFUNDED = "refunded", "Refunded"
        CANCELLED = "cancelled", "Cancelled"

    public_reference = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="product_purchases")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="purchases")
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.COMPLETED)
    ledger_transaction = models.OneToOneField(
        "wallets.LedgerTransaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="product_purchase",
    )
    delivery_note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["product", "status"]),
            models.Index(fields=["status", "-created_at"]),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gte=0), name="product_purchase_amount_non_negative"),
            models.UniqueConstraint(fields=["user", "product"], name="one_purchase_per_user_per_product"),
        ]

    def __str__(self):
        return f"{self.user} purchase of {self.product}"


class ProductCommission(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CREDITED = "credited", "Credited"
        REVERSED = "reversed", "Reversed"
        FLAGGED = "flagged", "Flagged"

    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="product_commissions",
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="generated_product_commissions",
    )
    purchase = models.OneToOneField(ProductPurchase, on_delete=models.PROTECT, related_name="commission")
    ledger_transaction = models.OneToOneField(
        "wallets.LedgerTransaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="product_commission",
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    release_at = models.DateTimeField()
    credited_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["referrer", "status"]),
            models.Index(fields=["status", "release_at"]),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="product_commission_amount_positive"),
        ]

    def __str__(self):
        return f"{self.referrer} commission for {self.purchase}"
