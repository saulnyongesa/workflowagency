from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from wallets.models import LedgerTransaction
from wallets.services import get_wallet, post_ledger_transaction
from .models import Product, ProductCommission, ProductPurchase


def money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_product_commission(product, purchase_amount):
    purchase_amount = money(purchase_amount)
    if product.commission_type == Product.CommissionType.NONE:
        return Decimal("0.00")
    if product.commission_type == Product.CommissionType.FIXED:
        return money(product.commission_amount)
    if product.commission_type == Product.CommissionType.PERCENT:
        return money(purchase_amount * product.commission_percent / Decimal("100"))
    return Decimal("0.00")


@transaction.atomic
def purchase_product(*, product, user):
    if user.status != user.AccountStatus.ACTIVE:
        raise ValidationError("Activate your account before purchasing products.")

    product = Product.objects.select_for_update().get(pk=product.pk)
    if not product.is_available:
        raise ValidationError("This product is not available for purchase.")
    if ProductPurchase.objects.filter(user=user, product=product, status=ProductPurchase.Status.COMPLETED).exists():
        raise ValidationError("You already purchased this product.")

    wallet = get_wallet(user)
    wallet.refresh_from_db()
    if wallet.available_balance < product.price:
        raise ValidationError("Available balance is not enough for this purchase.")

    purchase = ProductPurchase.objects.create(user=user, product=product, amount=product.price)
    ledger = None
    if product.price > 0:
        ledger, _ = post_ledger_transaction(
            user=user,
            amount=product.price,
            transaction_type=LedgerTransaction.TransactionType.PRODUCT_PURCHASE,
            direction=LedgerTransaction.Direction.DEBIT,
            balance_bucket=LedgerTransaction.BalanceBucket.AVAILABLE,
            description=f"Product purchase: {product.title}",
            idempotency_key=f"product-purchase-{purchase.pk}",
            source_app="products",
            source_model="ProductPurchase",
            source_id=str(purchase.pk),
        )
    purchase.ledger_transaction = ledger
    purchase.save(update_fields=["ledger_transaction", "updated_at"])

    product.sold_count += 1
    product.save(update_fields=["sold_count", "updated_at"])

    referrer = user.referred_by
    commission_amount = calculate_product_commission(product, product.price)
    if referrer and commission_amount > 0 and referrer != user:
        ProductCommission.objects.create(
            referrer=referrer,
            buyer=user,
            purchase=purchase,
            amount=commission_amount,
            release_at=timezone.now() + timezone.timedelta(hours=product.commission_release_delay_hours),
        )
    return purchase


@transaction.atomic
def release_product_commission(*, commission):
    commission = ProductCommission.objects.select_for_update().select_related("referrer", "purchase__product").get(
        pk=commission.pk
    )
    if commission.status == ProductCommission.Status.CREDITED:
        return commission, False
    if commission.status != ProductCommission.Status.PENDING:
        raise ValidationError("Only pending commissions can be released.")
    if commission.release_at > timezone.now():
        raise ValidationError("This commission is not ready for release.")

    ledger, _ = post_ledger_transaction(
        user=commission.referrer,
        amount=commission.amount,
        transaction_type=LedgerTransaction.TransactionType.PRODUCT_COMMISSION,
        direction=LedgerTransaction.Direction.CREDIT,
        balance_bucket=LedgerTransaction.BalanceBucket.AVAILABLE,
        description=f"Product commission for {commission.purchase.product.title}",
        idempotency_key=f"product-commission-{commission.pk}",
        source_app="products",
        source_model="ProductCommission",
        source_id=str(commission.pk),
    )
    commission.status = ProductCommission.Status.CREDITED
    commission.ledger_transaction = ledger
    commission.credited_at = timezone.now()
    commission.save(update_fields=["status", "ledger_transaction", "credited_at", "updated_at"])
    return commission, True


def release_due_product_commissions():
    released = 0
    due_commissions = ProductCommission.objects.filter(
        status=ProductCommission.Status.PENDING,
        release_at__lte=timezone.now(),
    )
    for commission in due_commissions:
        _, created = release_product_commission(commission=commission)
        if created:
            released += 1
    return released
