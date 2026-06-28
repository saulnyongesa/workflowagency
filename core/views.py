from django.contrib.auth.decorators import login_required
from django.db.models import F, Q
from django.shortcuts import render
from django.utils import timezone

from core.services import get_finance_settings
from jobs.models import Job
from wallets.services import get_wallet


def home(request):
    return render(request, "core/home.html")


@login_required
def dashboard(request):
    direct_referrals = request.user.direct_referrals.count()
    wallet = get_wallet(request.user)
    finance_settings = get_finance_settings()
    now = timezone.now()
    open_jobs = (
        Job.objects.filter(status=Job.Status.PUBLISHED, starts_at__lte=now, claims_count__lt=F("worker_limit"))
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gte=now))
        .select_related("category")
    )
    dashboard_stats = [
        {
            "label": "Available balance",
            "value": f"KES {wallet.available_balance}",
            "helper": "Ledger-backed wallet",
            "tone": "success",
        },
        {
            "label": "Open jobs",
            "value": open_jobs.count(),
            "helper": "Claimable published campaigns",
            "tone": "primary",
        },
        {
            "label": "Direct referrals",
            "value": direct_referrals,
            "helper": "People registered with your code",
            "tone": "info",
        },
        {
            "label": "Withdrawable",
            "value": f"KES {wallet.available_balance}",
            "helper": f"Minimum withdrawal: KES {finance_settings.minimum_withdrawal_amount}",
            "tone": "warning",
        },
    ]
    opportunities = [
        {
            "title": job.title,
            "category": job.category.name,
            "reward": f"KES {job.reward_amount}",
            "slots": f"{job.available_slots} slots",
            "status": job.get_job_type_display(),
            "url": job.get_absolute_url() if hasattr(job, "get_absolute_url") else None,
            "slug": job.slug,
        }
        for job in open_jobs[:3]
    ]
    context = {
        "dashboard_stats": dashboard_stats,
        "opportunities": opportunities,
        "wallet": wallet,
        "finance_settings": finance_settings,
    }
    return render(request, "core/dashboard.html", context)
