import json

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.services import get_finance_settings
from .forms import DepositForm, MpesaPhoneForm
from .models import MpesaTransaction
from .mpesa import MpesaConfigurationError, MpesaRequestError, register_c2b_urls
from .services import (
    callback_url,
    create_mpesa_transaction,
    find_user_from_account_reference,
    initiate_transaction_stk_push,
    process_failed_stk_callback,
    process_successful_mpesa_transaction,
)


@login_required
def activation_page(request):
    settings_obj = get_finance_settings()
    form = MpesaPhoneForm(request.POST or None, initial={"phone_number": request.user.phone_number})
    recent_transactions = request.user.mpesa_transactions.filter(
        transaction_kind=MpesaTransaction.TransactionKind.ACTIVATION
    )[:5]

    if request.method == "POST" and form.is_valid():
        transaction = create_mpesa_transaction(
            user=request.user,
            amount=settings_obj.activation_fee,
            phone_number=form.cleaned_data["phone_number"],
            transaction_kind=MpesaTransaction.TransactionKind.ACTIVATION,
            payment_method=MpesaTransaction.PaymentMethod.STK_PUSH,
        )
        try:
            initiate_transaction_stk_push(request=request, transaction=transaction)
        except (MpesaConfigurationError, MpesaRequestError) as exc:
            transaction.status = MpesaTransaction.Status.FAILED
            transaction.result_description = str(exc)[:255]
            transaction.save(update_fields=["status", "result_description", "updated_at"])
            messages.error(request, str(exc))
        else:
            messages.success(request, "STK Push sent. Complete payment on your phone.")
            return redirect("mpesa_transaction_detail", public_reference=transaction.public_reference)

    return render(
        request,
        "payments/activation.html",
        {"form": form, "finance_settings": settings_obj, "recent_transactions": recent_transactions},
    )


@login_required
def deposit_page(request):
    form = DepositForm(request.POST or None, initial={"phone_number": request.user.phone_number})
    recent_transactions = request.user.mpesa_transactions.filter(
        transaction_kind=MpesaTransaction.TransactionKind.DEPOSIT
    )[:10]

    if request.method == "POST" and form.is_valid():
        transaction = create_mpesa_transaction(
            user=request.user,
            amount=form.cleaned_data["amount"],
            phone_number=form.cleaned_data["phone_number"],
            transaction_kind=MpesaTransaction.TransactionKind.DEPOSIT,
            payment_method=MpesaTransaction.PaymentMethod.STK_PUSH,
        )
        try:
            initiate_transaction_stk_push(request=request, transaction=transaction)
        except (MpesaConfigurationError, MpesaRequestError) as exc:
            transaction.status = MpesaTransaction.Status.FAILED
            transaction.result_description = str(exc)[:255]
            transaction.save(update_fields=["status", "result_description", "updated_at"])
            messages.error(request, str(exc))
        else:
            messages.success(request, "STK Push sent. Complete payment on your phone.")
            return redirect("mpesa_transaction_detail", public_reference=transaction.public_reference)

    return render(
        request,
        "payments/deposit.html",
        {"form": form, "recent_transactions": recent_transactions},
    )


@login_required
def transaction_detail(request, public_reference):
    transaction = get_object_or_404(MpesaTransaction, public_reference=public_reference)
    if transaction.user != request.user and not request.user.is_staff:
        return redirect("dashboard")
    return render(request, "payments/transaction_detail.html", {"transaction": transaction})


@csrf_exempt
@require_POST
def mpesa_stk_callback(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Invalid JSON"}, status=400)

    callback = payload.get("Body", {}).get("stkCallback", {})
    checkout_request_id = callback.get("CheckoutRequestID")
    result_code = callback.get("ResultCode")
    result_description = callback.get("ResultDesc", "")
    if result_code != 0:
        process_failed_stk_callback(
            checkout_request_id=checkout_request_id,
            result_code=result_code,
            result_description=result_description,
            raw_callback=payload,
        )
        return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})

    transaction = MpesaTransaction.objects.filter(checkout_request_id=checkout_request_id).first()
    if not transaction:
        return JsonResponse({"ResultCode": 0, "ResultDesc": "Transaction not found"})

    metadata = {
        item.get("Name"): item.get("Value")
        for item in callback.get("CallbackMetadata", {}).get("Item", [])
    }
    try:
        process_successful_mpesa_transaction(
            transaction=transaction,
            mpesa_receipt_number=str(metadata.get("MpesaReceiptNumber", "")),
            paid_amount=metadata.get("Amount", transaction.amount),
            phone_number=str(metadata.get("PhoneNumber", transaction.phone_number)),
            raw_callback=payload,
            result_code=str(result_code),
            result_description=result_description or "Accepted",
        )
    except ValidationError:
        return JsonResponse({"ResultCode": 0, "ResultDesc": "Validation handled"})
    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})


@csrf_exempt
@require_POST
def c2b_validation(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"ResultCode": "C2B00016", "ResultDesc": "Invalid JSON"}, status=400)

    account_reference = str(payload.get("BillRefNumber", "")).strip().upper()
    transaction = MpesaTransaction.objects.filter(
        account_reference=account_reference,
        status__in=[MpesaTransaction.Status.INITIATED, MpesaTransaction.Status.PENDING],
    ).first()
    user, _ = find_user_from_account_reference(account_reference)
    if not transaction and not user:
        return JsonResponse({"ResultCode": "C2B00012", "ResultDesc": "Invalid account reference"})
    return JsonResponse({"ResultCode": "0", "ResultDesc": "Accepted"})


@csrf_exempt
@require_POST
def c2b_confirmation(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"ResultCode": "1", "ResultDesc": "Invalid JSON"}, status=400)

    receipt = str(payload.get("TransID", "")).strip()
    account_reference = str(payload.get("BillRefNumber", "")).strip().upper()
    paid_amount = payload.get("TransAmount") or "0"
    phone_number = str(payload.get("MSISDN", "")).strip()
    if receipt and MpesaTransaction.objects.filter(mpesa_receipt_number=receipt).exists():
        return JsonResponse({"ResultCode": "0", "ResultDesc": "Transaction already processed"})

    transaction = MpesaTransaction.objects.filter(
        account_reference=account_reference,
        status__in=[MpesaTransaction.Status.INITIATED, MpesaTransaction.Status.PENDING],
    ).first()
    if not transaction:
        user, kind = find_user_from_account_reference(account_reference)
        if not user or not kind:
            safe_amount = paid_amount
            try:
                if float(safe_amount) < 1:
                    safe_amount = 1
            except (TypeError, ValueError):
                safe_amount = 1
            MpesaTransaction.objects.create(
                user=None,
                transaction_kind=MpesaTransaction.TransactionKind.DEPOSIT,
                payment_method=MpesaTransaction.PaymentMethod.C2B,
                status=MpesaTransaction.Status.UNMATCHED,
                amount=safe_amount,
                phone_number=phone_number,
                account_reference=account_reference or "UNKNOWN",
                mpesa_receipt_number=receipt or None,
                raw_callback=payload,
            )
            return JsonResponse({"ResultCode": "0", "ResultDesc": "Unmatched transaction stored"})
        transaction = create_mpesa_transaction(
            user=user,
            amount=paid_amount,
            phone_number=phone_number,
            transaction_kind=kind,
            payment_method=MpesaTransaction.PaymentMethod.C2B,
        )

    try:
        process_successful_mpesa_transaction(
            transaction=transaction,
            mpesa_receipt_number=receipt,
            paid_amount=paid_amount,
            phone_number=phone_number,
            raw_callback=payload,
            result_code="0",
            result_description="C2B confirmation accepted",
        )
    except ValidationError:
        pass
    return JsonResponse({"ResultCode": "0", "ResultDesc": "Processed Successfully"})


@staff_member_required
def register_c2b_urls_view(request):
    if request.method == "POST":
        try:
            response_json, _ = register_c2b_urls(
                validation_url=callback_url(request, "mpesa_c2b_validation"),
                confirmation_url=callback_url(request, "mpesa_c2b_confirmation"),
            )
        except (MpesaConfigurationError, MpesaRequestError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"C2B URLs registration response: {response_json}")
            return redirect("register_c2b_urls")
    return render(
        request,
        "payments/register_c2b.html",
        {
            "validation_url": callback_url(request, "mpesa_c2b_validation"),
            "confirmation_url": callback_url(request, "mpesa_c2b_confirmation"),
        },
    )
