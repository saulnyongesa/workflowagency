from decimal import Decimal

from django.db.models import Sum

from core.services import get_finance_settings
from jobs.models import Job, JobClaim, JobSubmission
from payments.models import MpesaTransaction
from products.models import ProductCommission, ProductPurchase
from referrals.models import ReferralBonus
from wallets.models import LedgerTransaction, WithdrawalRequest
from wallets.services import confirmed_cash_total, wallet_liability_summary


ZERO = Decimal("0.00")


def aggregate_amount(queryset, field="amount"):
    return queryset.aggregate(total=Sum(field))["total"] or ZERO


def ledger_total(transaction_type, direction=None):
    queryset = LedgerTransaction.objects.filter(transaction_type=transaction_type)
    if direction:
        queryset = queryset.filter(direction=direction)
    return aggregate_amount(queryset)


def admin_finance_snapshot():
    finance_settings = get_finance_settings()
    liabilities = wallet_liability_summary()
    confirmed_cash = confirmed_cash_total()
    reserve_required = (liabilities["total"] * finance_settings.reserve_ratio_target) + finance_settings.minimum_platform_cash_buffer
    reserve_gap = confirmed_cash - reserve_required

    open_withdrawals = WithdrawalRequest.objects.filter(
        status__in=[
            WithdrawalRequest.Status.REQUESTED,
            WithdrawalRequest.Status.APPROVED,
            WithdrawalRequest.Status.PROCESSING,
        ]
    )
    pending_submissions = JobSubmission.objects.filter(status=JobClaim.Status.SUBMITTED).select_related("claim__job")
    pending_job_rewards = sum((submission.claim.job.reward_amount for submission in pending_submissions), ZERO)
    pending_referral_bonuses = aggregate_amount(ReferralBonus.objects.filter(status=ReferralBonus.Status.PENDING))
    pending_product_commissions = aggregate_amount(
        ProductCommission.objects.filter(status=ProductCommission.Status.PENDING)
    )

    activation_cash = aggregate_amount(
        MpesaTransaction.objects.filter(
            status=MpesaTransaction.Status.SUCCESS,
            transaction_kind=MpesaTransaction.TransactionKind.ACTIVATION,
        )
    )
    deposit_cash = aggregate_amount(
        MpesaTransaction.objects.filter(
            status=MpesaTransaction.Status.SUCCESS,
            transaction_kind=MpesaTransaction.TransactionKind.DEPOSIT,
        )
    )
    product_sales = aggregate_amount(ProductPurchase.objects.filter(status=ProductPurchase.Status.COMPLETED))
    job_rewards_paid = ledger_total(
        LedgerTransaction.TransactionType.JOB_REWARD_APPROVED,
        LedgerTransaction.Direction.CREDIT,
    )
    referral_rewards_paid = ledger_total(
        LedgerTransaction.TransactionType.REFERRAL_BONUS_AVAILABLE,
        LedgerTransaction.Direction.CREDIT,
    )
    product_commissions_paid = ledger_total(
        LedgerTransaction.TransactionType.PRODUCT_COMMISSION,
        LedgerTransaction.Direction.CREDIT,
    )
    withdrawals_paid = ledger_total(
        LedgerTransaction.TransactionType.WITHDRAWAL_PAID,
        LedgerTransaction.Direction.DEBIT,
    )

    return {
        "finance_settings": finance_settings,
        "liabilities": liabilities,
        "confirmed_cash": confirmed_cash,
        "reserve_required": reserve_required,
        "reserve_gap": reserve_gap,
        "ledger_count": LedgerTransaction.objects.count(),
        "open_withdrawal_count": open_withdrawals.count(),
        "open_withdrawal_total": aggregate_amount(open_withdrawals),
        "pending_submission_count": pending_submissions.count(),
        "pending_job_rewards": pending_job_rewards,
        "pending_referral_bonuses": pending_referral_bonuses,
        "pending_product_commissions": pending_product_commissions,
        "activation_cash": activation_cash,
        "deposit_cash": deposit_cash,
        "product_sales": product_sales,
        "job_rewards_paid": job_rewards_paid,
        "referral_rewards_paid": referral_rewards_paid,
        "product_commissions_paid": product_commissions_paid,
        "withdrawals_paid": withdrawals_paid,
        "open_jobs": Job.objects.filter(status=Job.Status.PUBLISHED).count(),
        "completed_purchases": ProductPurchase.objects.filter(status=ProductPurchase.Status.COMPLETED).count(),
    }
