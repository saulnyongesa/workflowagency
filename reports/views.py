import csv

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.forms.models import model_to_dict
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.models import AuditLog, FinanceSettings
from core.seed_content import DEFAULT_BULK_SEED_TARGETS, get_seed_status, start_bulk_content_seed
from core.services import create_audit_log
from jobs.models import Job, JobCategory
from payments.services import record_manual_activation
from products.models import Product, ProductCategory
from support.models import Announcement, FAQ, PolicyPage
from wallets.models import LedgerTransaction
from .forms import (
    AnnouncementManageForm,
    FAQManageForm,
    FinanceSettingsForm,
    JobCategoryForm,
    JobManageForm,
    ManualActivationForm,
    PolicyPageManageForm,
    ProductCategoryForm,
    ProductManageForm,
)
from .services import admin_finance_snapshot


User = get_user_model()


@staff_member_required
def admin_dashboard(request):
    snapshot = admin_finance_snapshot()
    report_cards = [
        {
            "label": "Confirmed cash",
            "value": f"KES {snapshot['confirmed_cash']}",
            "helper": "Successful M-Pesa receipts",
            "tone": "success",
        },
        {
            "label": "Wallet liability",
            "value": f"KES {snapshot['liabilities']['total']}",
            "helper": "Available + pending + locked",
            "tone": "warning",
        },
        {
            "label": "Reserve gap",
            "value": f"KES {snapshot['reserve_gap']}",
            "helper": f"Required: KES {snapshot['reserve_required']}",
            "tone": "success" if snapshot["reserve_gap"] >= 0 else "danger",
        },
        {
            "label": "Pending rewards",
            "value": f"KES {snapshot['pending_job_rewards'] + snapshot['pending_referral_bonuses'] + snapshot['pending_product_commissions']}",
            "helper": "Jobs + referrals + product commissions",
            "tone": "primary",
        },
    ]
    recent_ledger = LedgerTransaction.objects.select_related("user")[:15]
    seed_status = get_seed_status()
    return render(
        request,
        "reports/admin_dashboard.html",
        {
            "report_cards": report_cards,
            "finance_settings": snapshot["finance_settings"],
            "snapshot": snapshot,
            "liabilities": snapshot["liabilities"],
            "recent_ledger": recent_ledger,
            "seed_status": seed_status,
            "seed_targets": DEFAULT_BULK_SEED_TARGETS,
        },
    )


@staff_member_required
def export_ledger_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="ledger-export.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            "created_at",
            "user",
            "transaction_type",
            "direction",
            "bucket",
            "amount",
            "status",
            "description",
            "source_app",
            "source_model",
            "source_id",
        ]
    )
    queryset = LedgerTransaction.objects.select_related("user").order_by("-created_at")[:5000]
    for transaction_item in queryset:
        writer.writerow(
            [
                transaction_item.created_at.isoformat(),
                transaction_item.user.username,
                transaction_item.transaction_type,
                transaction_item.direction,
                transaction_item.balance_bucket,
                transaction_item.amount,
                transaction_item.status,
                transaction_item.description,
                transaction_item.source_app,
                transaction_item.source_model,
                transaction_item.source_id,
            ]
        )
    return response


def _audit_finance_settings_change(request, before_obj, after_obj):
    before = model_to_dict(before_obj)
    after = model_to_dict(after_obj)
    changes = {}
    for field, value in after.items():
        if field == "updated_by":
            continue
        if str(before.get(field)) != str(value):
            changes[field] = {"old": str(before.get(field)), "new": str(value)}
    if changes:
        create_audit_log(
            action=AuditLog.Action.FINANCE_SETTING_CHANGED,
            actor=request.user,
            instance=after_obj,
            changes=changes,
            request=request,
        )


def _finance_settings_defaults():
    defaults = {}
    for field_name in FinanceSettingsForm.Meta.fields:
        model_field = FinanceSettings._meta.get_field(field_name)
        defaults[field_name] = model_field.get_default()
    return defaults


@staff_member_required
def admin_finance_settings(request):
    settings_obj = FinanceSettings.load()
    before_obj = FinanceSettings.objects.get(pk=settings_obj.pk)
    if request.method == "POST" and request.POST.get("form_type") == "reset_defaults":
        for field_name, value in _finance_settings_defaults().items():
            setattr(settings_obj, field_name, value)
        settings_obj.updated_by = request.user
        settings_obj.save()
        _audit_finance_settings_change(request, before_obj, settings_obj)
        messages.success(request, "Finance settings reset to defaults.")
        return redirect("admin_finance_settings")

    form = FinanceSettingsForm(request.POST or None, instance=settings_obj)
    if request.method == "POST" and form.is_valid():
        settings_item = form.save(commit=False)
        settings_item.updated_by = request.user
        settings_item.save()
        _audit_finance_settings_change(request, before_obj, settings_item)
        messages.success(request, "Finance settings updated.")
        return redirect("admin_finance_settings")
    return render(request, "reports/admin_finance_settings.html", {"form": form})


@staff_member_required
@require_POST
def admin_toggle_job_claims(request):
    settings_obj = FinanceSettings.load()
    before_obj = FinanceSettings.objects.get(pk=settings_obj.pk)
    should_enable = request.POST.get("job_claims_enabled") == "1"
    settings_obj.job_claims_enabled = should_enable
    settings_obj.updated_by = request.user
    settings_obj.save()
    _audit_finance_settings_change(request, before_obj, settings_obj)
    if should_enable:
        messages.success(request, "Job claiming enabled.")
    else:
        messages.warning(request, "All job claims are disabled. Active users will see the temporary availability message.")
    return redirect(request.POST.get("next") or "admin_dashboard")


@staff_member_required
@require_POST
def admin_toggle_chat_sessions(request):
    settings_obj = FinanceSettings.load()
    before_obj = FinanceSettings.objects.get(pk=settings_obj.pk)
    should_enable = request.POST.get("chat_sessions_enabled") == "1"
    settings_obj.chat_sessions_enabled = should_enable
    settings_obj.updated_by = request.user
    settings_obj.save()
    _audit_finance_settings_change(request, before_obj, settings_obj)
    if should_enable:
        messages.success(request, "Chat sessions enabled.")
    else:
        messages.warning(request, "Chat sessions are disabled. Users will see the temporary availability message.")
    return redirect(request.POST.get("next") or "admin_dashboard")


@staff_member_required
@require_POST
def admin_seed_demo_content(request):
    def seed_count(name):
        try:
            value = int(request.POST.get(name) or DEFAULT_BULK_SEED_TARGETS[name])
        except (TypeError, ValueError):
            value = DEFAULT_BULK_SEED_TARGETS[name]
        return max(0, min(value, 50000))

    jobs = seed_count("jobs")
    surveys = seed_count("surveys")
    products = seed_count("products")
    started = start_bulk_content_seed(
        actor_id=request.user.pk,
        jobs=jobs,
        surveys=surveys,
        products=products,
    )
    if started:
        messages.success(request, "Content generation has started. Refresh this page to see progress.")
    else:
        messages.warning(request, "Content generation is already running.")
    return redirect("admin_dashboard")


@staff_member_required
def admin_jobs_manager(request):
    category_form = JobCategoryForm(request.POST or None, prefix="category")
    if request.method == "POST" and request.POST.get("form_type") == "category" and category_form.is_valid():
        category_form.save()
        messages.success(request, "Job category saved.")
        return redirect("admin_jobs_manager")

    jobs = Job.objects.select_related("category")[:30]
    categories = JobCategory.objects.all()
    return render(
        request,
        "reports/admin_jobs_manager.html",
        {
            "jobs": jobs,
            "categories": categories,
            "category_form": category_form,
            "finance_settings": FinanceSettings.load(),
        },
    )


@staff_member_required
def admin_job_form(request, job_id=None):
    job = get_object_or_404(Job, pk=job_id) if job_id else None
    form = JobManageForm(request.POST or None, request.FILES or None, instance=job)
    if request.method == "POST" and form.is_valid():
        saved_job = form.save(commit=False)
        if not saved_job.created_by:
            saved_job.created_by = request.user
        saved_job.save()
        messages.success(request, "Job saved.")
        return redirect("admin_jobs_manager")
    return render(request, "reports/admin_job_form.html", {"form": form, "job": job})


@staff_member_required
def admin_users_manager(request):
    activation_form = ManualActivationForm()
    if request.method == "POST" and request.POST.get("form_type") == "manual_activation":
        activation_form = ManualActivationForm(request.POST)
        if activation_form.is_valid():
            user = activation_form.cleaned_data["user"]
            try:
                mpesa_transaction = record_manual_activation(
                    user=user,
                    admin_user=request.user,
                    request=request,
                )
            except ValidationError as exc:
                activation_form.add_error(None, exc)
            else:
                messages.success(
                    request,
                    f"{user.username} activated. Activation fee recorded as {mpesa_transaction.mpesa_receipt_number}.",
                )
                return redirect("admin_users_manager")

    users = User.objects.select_related("referred_by").order_by("-date_joined")[:80]
    return render(
        request,
        "reports/admin_users_manager.html",
        {
            "activation_form": activation_form,
            "finance_settings": FinanceSettings.load(),
            "users": users,
        },
    )


@staff_member_required
def admin_products_manager(request):
    category_form = ProductCategoryForm(request.POST or None, prefix="category")
    if request.method == "POST" and request.POST.get("form_type") == "category" and category_form.is_valid():
        category_form.save()
        messages.success(request, "Product category saved.")
        return redirect("admin_products_manager")

    products = Product.objects.select_related("category")[:30]
    categories = ProductCategory.objects.all()
    return render(
        request,
        "reports/admin_products_manager.html",
        {"products": products, "categories": categories, "category_form": category_form},
    )


@staff_member_required
def admin_product_form(request, product_id=None):
    product = get_object_or_404(Product, pk=product_id) if product_id else None
    form = ProductManageForm(request.POST or None, request.FILES or None, instance=product)
    if request.method == "POST" and form.is_valid():
        saved_product = form.save(commit=False)
        if not saved_product.created_by:
            saved_product.created_by = request.user
        saved_product.save()
        messages.success(request, "Product saved.")
        return redirect("admin_products_manager")
    return render(request, "reports/admin_product_form.html", {"form": form, "product": product})


@staff_member_required
def admin_content_manager(request):
    announcement_form = AnnouncementManageForm(prefix="announcement")
    faq_form = FAQManageForm(prefix="faq")
    policy_form = PolicyPageManageForm(prefix="policy")

    if request.method == "POST":
        form_type = request.POST.get("form_type")
        if form_type == "announcement":
            announcement_form = AnnouncementManageForm(request.POST, prefix="announcement")
            if announcement_form.is_valid():
                announcement = announcement_form.save(commit=False)
                if not announcement.created_by:
                    announcement.created_by = request.user
                announcement.save()
                messages.success(request, "Announcement saved.")
                return redirect("admin_content_manager")
        elif form_type == "faq":
            faq_form = FAQManageForm(request.POST, prefix="faq")
            if faq_form.is_valid():
                faq_form.save()
                messages.success(request, "FAQ saved.")
                return redirect("admin_content_manager")
        elif form_type == "policy":
            policy_form = PolicyPageManageForm(request.POST, prefix="policy")
            if policy_form.is_valid():
                policy = policy_form.save(commit=False)
                policy.updated_by = request.user
                policy.save()
                messages.success(request, "Policy saved.")
                return redirect("admin_content_manager")

    return render(
        request,
        "reports/admin_content_manager.html",
        {
            "announcement_form": announcement_form,
            "faq_form": faq_form,
            "policy_form": policy_form,
            "announcements": Announcement.objects.all()[:10],
            "faqs": FAQ.objects.all()[:10],
            "policies": PolicyPage.objects.all()[:10],
        },
    )


@staff_member_required
def admin_content_edit(request, content_type, object_id):
    config = {
        "announcement": (Announcement, AnnouncementManageForm, "Announcement"),
        "faq": (FAQ, FAQManageForm, "FAQ"),
        "policy": (PolicyPage, PolicyPageManageForm, "Policy"),
    }
    if content_type not in config:
        return redirect("admin_content_manager")
    model, form_class, label = config[content_type]
    instance = get_object_or_404(model, pk=object_id)
    form = form_class(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        content_item = form.save(commit=False)
        if isinstance(content_item, Announcement) and not content_item.created_by:
            content_item.created_by = request.user
        if isinstance(content_item, PolicyPage):
            content_item.updated_by = request.user
        content_item.save()
        messages.success(request, f"{label} updated.")
        return redirect("admin_content_manager")
    return render(
        request,
        "reports/admin_content_form.html",
        {"form": form, "content_type": content_type, "label": label, "content_item": instance},
    )
