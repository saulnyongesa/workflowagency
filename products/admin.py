from django.contrib import admin
from django.core.exceptions import ValidationError

from .models import Product, ProductCategory, ProductCommission, ProductPurchase
from .services import release_product_commission


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "product_type", "content_format", "status", "price", "sold_count", "commission_type")
    list_filter = ("status", "product_type", "content_format", "commission_type", "category")
    search_fields = ("title", "summary", "description")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("sold_count", "created_at", "updated_at")
    actions = ("publish_products", "pause_products")
    fieldsets = (
        (
            "Product",
            {
                "fields": (
                    "category",
                    "title",
                    "slug",
                    "product_type",
                    "content_format",
                    "status",
                    "summary",
                    "description",
                    "price",
                )
            },
        ),
        ("Delivery", {"fields": ("cover_image", "download_file", "external_url", "stock_quantity", "sold_count")}),
        (
            "Commission",
            {"fields": ("commission_type", "commission_amount", "commission_percent", "commission_release_delay_hours")},
        ),
        ("Ownership", {"fields": ("created_by", "created_at", "updated_at")}),
    )

    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="Publish selected products")
    def publish_products(self, request, queryset):
        queryset.update(status=Product.Status.PUBLISHED)

    @admin.action(description="Pause selected products")
    def pause_products(self, request, queryset):
        queryset.update(status=Product.Status.PAUSED)


@admin.register(ProductPurchase)
class ProductPurchaseAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "product", "amount", "status")
    list_filter = ("status", "created_at", "product__category")
    search_fields = ("user__username", "user__email", "product__title", "public_reference")
    readonly_fields = (
        "public_reference",
        "user",
        "product",
        "amount",
        "status",
        "ledger_transaction",
        "delivery_note",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False


@admin.register(ProductCommission)
class ProductCommissionAdmin(admin.ModelAdmin):
    list_display = ("created_at", "referrer", "buyer", "purchase", "amount", "status", "release_at")
    list_filter = ("status", "release_at", "created_at")
    search_fields = ("referrer__username", "buyer__username", "purchase__product__title")
    readonly_fields = (
        "referrer",
        "buyer",
        "purchase",
        "ledger_transaction",
        "amount",
        "status",
        "release_at",
        "credited_at",
        "created_at",
        "updated_at",
    )
    actions = ("release_selected_commissions",)

    def has_add_permission(self, request):
        return False

    @admin.action(description="Release due selected commissions")
    def release_selected_commissions(self, request, queryset):
        released = 0
        for commission in queryset:
            try:
                _, created = release_product_commission(commission=commission)
            except ValidationError:
                continue
            if created:
                released += 1
        self.message_user(request, f"Released {released} product commission(s).")
