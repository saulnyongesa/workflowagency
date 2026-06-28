from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from core.services import get_finance_settings
from jobs.models import Job, JobClaim, JobSubmission
from wallets.models import LedgerTransaction
from wallets.models import WithdrawalRequest
from wallets.services import confirmed_cash_total, wallet_liability_summary


@staff_member_required
def admin_dashboard(request):
    finance_settings = get_finance_settings()
    liabilities = wallet_liability_summary()
    confirmed_cash = confirmed_cash_total()
    ledger_count = LedgerTransaction.objects.count()
    open_withdrawals = WithdrawalRequest.objects.filter(
        status__in=[
            WithdrawalRequest.Status.REQUESTED,
            WithdrawalRequest.Status.APPROVED,
            WithdrawalRequest.Status.PROCESSING,
        ]
    )
    open_withdrawal_total = sum(withdrawal.amount for withdrawal in open_withdrawals)
    pending_submissions = JobSubmission.objects.filter(status=JobClaim.Status.SUBMITTED).count()
    open_jobs = Job.objects.filter(status=Job.Status.PUBLISHED).count()
    report_cards = [
        {
            "label": "Confirmed cash",
            "value": f"KES {confirmed_cash}",
            "helper": "Successful M-Pesa receipts",
            "tone": "success",
        },
        {
            "label": "Wallet liability",
            "value": f"KES {liabilities['total']}",
            "helper": "Available + pending + locked",
            "tone": "warning",
        },
        {
            "label": "Open withdrawals",
            "value": f"KES {open_withdrawal_total}",
            "helper": f"{open_withdrawals.count()} requests need action",
            "tone": "danger",
        },
        {
            "label": "Pending job proof",
            "value": pending_submissions,
            "helper": f"{open_jobs} published jobs",
            "tone": "primary",
        },
    ]
    return render(
        request,
        "reports/admin_dashboard.html",
        {
            "report_cards": report_cards,
            "finance_settings": finance_settings,
            "liabilities": liabilities,
            "confirmed_cash": confirmed_cash,
            "ledger_count": ledger_count,
            "open_withdrawal_total": open_withdrawal_total,
            "open_withdrawal_count": open_withdrawals.count(),
            "pending_submissions": pending_submissions,
        },
    )
