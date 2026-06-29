from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from wallets.models import LedgerTransaction
from wallets.services import get_wallet, post_ledger_transaction
from .models import Product, ProductCategory, ProductCommission, ProductPurchase
from .services import purchase_product, release_product_commission


User = get_user_model()


class ProductStoreTests(TestCase):
    def setUp(self):
        self.referrer = User.objects.create_user(
            username="productref",
            email="productref@example.com",
            phone_number="254711100001",
            password="StrongPass123!",
            status=User.AccountStatus.ACTIVE,
            activation_status=User.ActivationStatus.ACTIVATED,
        )
        self.buyer = User.objects.create_user(
            username="productbuyer",
            email="productbuyer@example.com",
            phone_number="254711100002",
            password="StrongPass123!",
            referred_by=self.referrer,
            status=User.AccountStatus.ACTIVE,
            activation_status=User.ActivationStatus.ACTIVATED,
        )
        self.category = ProductCategory.objects.create(name="Guides", slug="guides")
        self.product = Product.objects.create(
            category=self.category,
            title="Online work starter guide",
            slug="online-work-starter-guide",
            product_type=Product.ProductType.EXTERNAL_LINK,
            status=Product.Status.PUBLISHED,
            summary="A compact guide for new online workers.",
            description="Guide content and delivery instructions.",
            price=Decimal("120.00"),
            external_url="https://example.com/guide",
            commission_type=Product.CommissionType.FIXED,
            commission_amount=Decimal("20.00"),
            commission_release_delay_hours=24,
        )
        post_ledger_transaction(
            user=self.buyer,
            amount="500.00",
            transaction_type=LedgerTransaction.TransactionType.DEPOSIT_CONFIRMED,
            direction=LedgerTransaction.Direction.CREDIT,
            balance_bucket=LedgerTransaction.BalanceBucket.AVAILABLE,
            description="Test wallet funding",
        )

    def test_product_list_renders_published_product(self):
        self.client.force_login(self.buyer)

        response = self.client.get(reverse("product_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Online work starter guide")

    def test_purchase_debits_wallet_and_creates_commission(self):
        purchase = purchase_product(product=self.product, user=self.buyer)

        wallet = get_wallet(self.buyer)
        self.product.refresh_from_db()
        self.assertEqual(purchase.amount, Decimal("120.00"))
        self.assertEqual(wallet.available_balance, Decimal("380.00"))
        self.assertEqual(self.product.sold_count, 1)
        self.assertEqual(ProductCommission.objects.filter(purchase=purchase).count(), 1)

    def test_duplicate_purchase_is_blocked(self):
        purchase_product(product=self.product, user=self.buyer)

        with self.assertRaises(ValidationError):
            purchase_product(product=self.product, user=self.buyer)

    def test_release_due_product_commission_credits_referrer(self):
        purchase = purchase_product(product=self.product, user=self.buyer)
        commission = purchase.commission
        commission.release_at = timezone.now() - timezone.timedelta(minutes=1)
        commission.save(update_fields=["release_at"])

        released, created = release_product_commission(commission=commission)

        referrer_wallet = get_wallet(self.referrer)
        self.assertTrue(created)
        self.assertEqual(released.status, ProductCommission.Status.CREDITED)
        self.assertEqual(referrer_wallet.available_balance, Decimal("20.00"))
        self.assertEqual(referrer_wallet.total_earned, Decimal("20.00"))

    def test_purchase_view_creates_library_item(self):
        self.client.force_login(self.buyer)

        response = self.client.post(reverse("purchase_product", kwargs={"slug": self.product.slug}))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(ProductPurchase.objects.filter(user=self.buyer, product=self.product).count(), 1)
