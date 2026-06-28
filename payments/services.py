from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from core.services import get_finance_settings
from referrals.services import create_referral_bonus_for_activation
from wallets.models import LedgerTransaction
from wallets.services import post_ledger_transaction
from .models import MpesaTransaction
from .mpesa import initiate_stk_push, normalize_phone_number


def money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def build_account_reference(kind, user):
    prefix = "ACT" if kind == MpesaTransaction.TransactionKind.ACTIVATION else "DEP"
    return f"{prefix}{user.pk:06d}"


def callback_url(request, name):
    from django.conf import settings

    base_url = settings.MPESA_CALLBACK_BASE_URL.rstrip("/")
    path = reverse(name)
    if base_url:
        return f"{base_url}{path}"
    return request.build_absolute_uri(path)


def create_mpesa_transaction(*, user, amount, phone_number, transaction_kind, payment_method):
    amount = money(amount)
    if amount < Decimal("1.00"):
        raise ValidationError("M-Pesa amount must be at least KES 1.")
    phone_number = normalize_phone_number(phone_number)
    account_reference = build_account_reference(transaction_kind, user)
    return MpesaTransaction.objects.create(
        user=user,
        amount=amount,
        phone_number=phone_number,
        transaction_kind=transaction_kind,
        payment_method=payment_method,
        account_reference=account_reference,
    )


def initiate_transaction_stk_push(*, request, transaction):
    response_json, raw_request = initiate_stk_push(
        phone_number=transaction.phone_number,
        amount=transaction.amount,
        account_reference=transaction.account_reference,
        callback_url=callback_url(request, "mpesa_stk_callback"),
        description=f"Workflow Agency {transaction.get_transaction_kind_display()}",
    )
    transaction.raw_request = raw_request
    transaction.merchant_request_id = response_json.get("MerchantRequestID") or None
    transaction.checkout_request_id = response_json.get("CheckoutRequestID") or None
    response_code = str(response_json.get("ResponseCode", ""))
    transaction.status = (
        MpesaTransaction.Status.PENDING if response_code == "0" else MpesaTransaction.Status.FAILED
    )
    transaction.result_code = response_code
    transaction.result_description = response_json.get("ResponseDescription", "")
    transaction.save(
        update_fields=[
            "raw_request",
            "merchant_request_id",
            "checkout_request_id",
            "status",
            "result_code",
            "result_description",
            "updated_at",
        ]
    )
    return transaction


def _activation_credit_entries(transaction, settings_obj):
    activation_fee = transaction.amount
    if settings_obj.activation_credit_mode == settings_obj.ActivationCreditMode.WITHDRAWABLE_BALANCE:
        return [(LedgerTransaction.BalanceBucket.AVAILABLE, activation_fee)]
    if settings_obj.activation_credit_mode == settings_obj.ActivationCreditMode.PLATFORM_CREDIT:
        return [(LedgerTransaction.BalanceBucket.LOCKED, activation_fee)]

    available = min(settings_obj.activation_withdrawable_amount, activation_fee)
    locked = activation_fee - available
    entries = []
    if available > 0:
        entries.append((LedgerTransaction.BalanceBucket.AVAILABLE, available))
    if locked > 0:
        entries.append((LedgerTransaction.BalanceBucket.LOCKED, locked))
    return entries


@transaction.atomic
def process_successful_mpesa_transaction(
    *,
    transaction,
    mpesa_receipt_number,
    paid_amount,
    phone_number="",
    raw_callback=None,
    result_code="0",
    result_description="Accepted",
):
    transaction = MpesaTransaction.objects.select_for_update().get(pk=transaction.pk)
    if transaction.status == MpesaTransaction.Status.SUCCESS:
        return transaction, False

    if not mpesa_receipt_number:
        raise ValidationError("M-Pesa receipt number is required.")

    paid_amount = money(paid_amount)
    if paid_amount < transaction.amount:
        transaction.status = MpesaTransaction.Status.FAILED
        transaction.result_code = result_code
        transaction.result_description = "Paid amount is less than expected."
        transaction.raw_callback = raw_callback or {}
        transaction.processed_at = timezone.now()
        transaction.save()
        raise ValidationError("Paid amount is less than expected.")

    duplicate = (
        MpesaTransaction.objects.filter(mpesa_receipt_number=mpesa_receipt_number)
        .exclude(pk=transaction.pk)
        .exists()
    )
    if duplicate:
        return transaction, False

    transaction.mpesa_receipt_number = mpesa_receipt_number
    transaction.phone_number = normalize_phone_number(phone_number or transaction.phone_number)
    transaction.status = MpesaTransaction.Status.SUCCESS
    transaction.result_code = result_code
    transaction.result_description = result_description[:255]
    transaction.raw_callback = raw_callback or {}
    transaction.confirmed_at = timezone.now()
    transaction.processed_at = timezone.now()
    transaction.save()

    if transaction.user and transaction.transaction_kind == MpesaTransaction.TransactionKind.ACTIVATION:
        activate_user_from_transaction(transaction)
    elif transaction.user and transaction.transaction_kind == MpesaTransaction.TransactionKind.DEPOSIT:
        post_ledger_transaction(
            user=transaction.user,
            amount=transaction.amount,
            transaction_type=LedgerTransaction.TransactionType.DEPOSIT_CONFIRMED,
            direction=LedgerTransaction.Direction.CREDIT,
            balance_bucket=LedgerTransaction.BalanceBucket.AVAILABLE,
            description=f"M-Pesa deposit {transaction.mpesa_receipt_number}",
            idempotency_key=f"mpesa-deposit-{transaction.pk}",
            source_app="payments",
            source_model="MpesaTransaction",
            source_id=str(transaction.pk),
        )

    return transaction, True


def activate_user_from_transaction(transaction):
    user = transaction.user
    settings_obj = get_finance_settings()
    for bucket, amount in _activation_credit_entries(transaction, settings_obj):
        post_ledger_transaction(
            user=user,
            amount=amount,
            transaction_type=LedgerTransaction.TransactionType.ACTIVATION_CREDIT,
            direction=LedgerTransaction.Direction.CREDIT,
            balance_bucket=bucket,
            description=f"Activation credit from {transaction.mpesa_receipt_number or transaction.public_reference}",
            idempotency_key=f"activation-credit-{bucket}-{transaction.pk}",
            source_app="payments",
            source_model="MpesaTransaction",
            source_id=str(transaction.pk),
        )
    if user.status != User.AccountStatus.SUSPENDED:
        user.status = User.AccountStatus.ACTIVE
    user.activation_status = User.ActivationStatus.ACTIVATED
    user.save(update_fields=["status", "activation_status"])
    create_referral_bonus_for_activation(user, transaction)


def process_failed_stk_callback(*, checkout_request_id, result_code, result_description, raw_callback):
    transaction = MpesaTransaction.objects.filter(checkout_request_id=checkout_request_id).first()
    if not transaction:
        return None
    if transaction.status == MpesaTransaction.Status.SUCCESS:
        return transaction
    transaction.status = MpesaTransaction.Status.CANCELLED if str(result_code) == "1032" else MpesaTransaction.Status.FAILED
    transaction.result_code = str(result_code)
    transaction.result_description = str(result_description)[:255]
    transaction.raw_callback = raw_callback
    transaction.processed_at = timezone.now()
    transaction.save()
    return transaction


def find_user_from_account_reference(account_reference):
    prefix = str(account_reference)[:3].upper()
    user_id = str(account_reference)[3:]
    if prefix not in {"ACT", "DEP"} or not user_id.isdigit():
        return None, None
    kind = MpesaTransaction.TransactionKind.ACTIVATION if prefix == "ACT" else MpesaTransaction.TransactionKind.DEPOSIT
    UserModel = get_user_model()
    return UserModel.objects.filter(pk=int(user_id)).first(), kind
