from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.services import get_finance_settings
from .forms import AdminWalletAdjustmentForm, WithdrawalPaidForm, WithdrawalRejectForm, WithdrawalRequestForm
from .models import LedgerTransaction, WithdrawalRequest
from .services import (
    approve_withdrawal,
    get_wallet,
    mark_withdrawal_paid,
    post_admin_adjustment,
    reject_withdrawal,
    request_withdrawal,
)


@login_required
def wallet_dashboard(request):
    wallet = get_wallet(request.user)
    transactions = wallet.ledger_transactions.select_related("created_by")[:25]
    withdrawals = request.user.withdrawal_requests.all()[:10]
    return render(
        request,
        "wallets/wallet_dashboard.html",
        {"wallet": wallet, "transactions": transactions, "withdrawals": withdrawals},
    )


@login_required
def withdrawal_request_view(request):
    wallet = get_wallet(request.user)
    finance_settings = get_finance_settings()
    can_request_withdrawal = wallet.available_balance >= finance_settings.minimum_withdrawal_amount
    form = WithdrawalRequestForm(request.POST or None, initial_phone=request.user.phone_number or "")
    if request.method == "POST" and form.is_valid():
        try:
            withdrawal = request_withdrawal(
                user=request.user,
                amount=form.cleaned_data["amount"],
                phone_number=form.cleaned_data["phone_number"],
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Withdrawal request submitted for admin review.")
            return redirect("withdrawal_detail", pk=withdrawal.pk)
    withdrawals = request.user.withdrawal_requests.all()[:8]
    return render(
        request,
        "wallets/withdrawal_request.html",
        {
            "form": form,
            "wallet": wallet,
            "finance_settings": finance_settings,
            "can_request_withdrawal": can_request_withdrawal,
            "withdrawals": withdrawals,
        },
    )


@login_required
def withdrawal_history(request):
    withdrawals = request.user.withdrawal_requests.all()
    return render(request, "wallets/withdrawal_history.html", {"withdrawals": withdrawals})


@login_required
def withdrawal_detail(request, pk):
    withdrawal = get_object_or_404(WithdrawalRequest.objects.select_related("user", "reviewed_by"), pk=pk)
    if withdrawal.user != request.user and not request.user.is_staff:
        return redirect("wallet_dashboard")
    return render(request, "wallets/withdrawal_detail.html", {"withdrawal": withdrawal})


@staff_member_required
def admin_wallet_adjustment(request):
    form = AdminWalletAdjustmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            post_admin_adjustment(
                user=form.cleaned_data["user"],
                amount=form.cleaned_data["amount"],
                direction=form.cleaned_data["direction"],
                balance_bucket=form.cleaned_data["balance_bucket"],
                reason=form.cleaned_data["reason"],
                admin_user=request.user,
                request=request,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Wallet adjustment posted to the ledger.")
            return redirect("admin_wallet_adjustment")

    recent_adjustments = LedgerTransaction.objects.filter(
        transaction_type=LedgerTransaction.TransactionType.ADMIN_ADJUSTMENT
    ).select_related("user", "created_by")[:15]
    return render(
        request,
        "wallets/admin_adjustment.html",
        {"form": form, "recent_adjustments": recent_adjustments},
    )


@staff_member_required
def withdrawal_queue(request):
    withdrawals = WithdrawalRequest.objects.filter(
        status__in=[
            WithdrawalRequest.Status.REQUESTED,
            WithdrawalRequest.Status.APPROVED,
            WithdrawalRequest.Status.PROCESSING,
        ]
    ).select_related("user", "reviewed_by")
    paid_form = WithdrawalPaidForm()
    return render(
        request,
        "wallets/withdrawal_queue.html",
        {"withdrawals": withdrawals, "paid_form": paid_form},
    )


@staff_member_required
@require_POST
def approve_withdrawal_view(request, pk):
    withdrawal = get_object_or_404(WithdrawalRequest, pk=pk)
    try:
        approve_withdrawal(withdrawal=withdrawal, reviewer=request.user, request=request)
    except ValidationError as exc:
        messages.error(request, exc.messages[0] if hasattr(exc, "messages") else str(exc))
    else:
        messages.success(request, "Withdrawal approved.")
    return redirect("withdrawal_queue")


@staff_member_required
@require_POST
def mark_withdrawal_paid_view(request, pk):
    withdrawal = get_object_or_404(WithdrawalRequest, pk=pk)
    form = WithdrawalPaidForm(request.POST)
    if form.is_valid():
        try:
            mark_withdrawal_paid(
                withdrawal=withdrawal,
                reviewer=request.user,
                payout_reference=form.cleaned_data["payout_reference"],
                request=request,
            )
        except ValidationError as exc:
            messages.error(request, exc.messages[0] if hasattr(exc, "messages") else str(exc))
        else:
            messages.success(request, "Withdrawal marked as paid.")
    else:
        messages.error(request, "Payout reference is invalid.")
    return redirect("withdrawal_queue")


@staff_member_required
def reject_withdrawal_view(request, pk):
    withdrawal = get_object_or_404(WithdrawalRequest.objects.select_related("user"), pk=pk)
    form = WithdrawalRejectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            reject_withdrawal(
                withdrawal=withdrawal,
                reviewer=request.user,
                reason=form.cleaned_data["reason"],
                request=request,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Withdrawal rejected and funds returned.")
            return redirect("withdrawal_queue")
    return render(request, "wallets/reject_withdrawal.html", {"withdrawal": withdrawal, "form": form})
