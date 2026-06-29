import shutil
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from core.models import FinanceSettings
from wallets.models import LedgerTransaction
from wallets.services import get_wallet, post_ledger_transaction


DEMO_PASSWORDS = {
    "demo_admin": "DemoAdmin123!",
    "demo_referrer": "DemoUser123!",
    "demo_worker": "DemoUser123!",
    "demo_locked": "DemoUser123!",
}


class Command(BaseCommand):
    help = "Prepare a bundled SQLite database for the Vercel client prototype."

    def add_arguments(self, parser):
        parser.add_argument("--jobs", type=int, default=5000, help="Target number of non-survey demo jobs.")
        parser.add_argument("--surveys", type=int, default=5000, help="Target number of demo surveys.")
        parser.add_argument("--products", type=int, default=5000, help="Target number of demo products.")
        parser.add_argument("--batch-size", type=int, default=1000, help="Bulk insert batch size.")
        parser.add_argument("--seed", type=int, default=20260629, help="Deterministic data seed.")
        parser.add_argument("--reset-samples", action="store_true", help="Delete generated marketplace rows first.")
        parser.add_argument("--skip-support-content", action="store_true", help="Do not seed prototype FAQs and policies.")
        parser.add_argument(
            "--prototype-file",
            default="prototype.sqlite3",
            help="SQLite file to write at the repository root.",
        )
        parser.add_argument("--skip-copy", action="store_true", help="Prepare data without copying a prototype file.")

    def handle(self, *args, **options):
        users = self._ensure_demo_users()
        self._ensure_demo_finance_settings(users["demo_admin"])
        self._ensure_demo_balances(users)

        call_command(
            "seed_sample_marketplace",
            jobs=max(options["jobs"], 0),
            surveys=max(options["surveys"], 0),
            products=max(options["products"], 0),
            batch_size=max(options["batch_size"], 1),
            seed=options["seed"],
            reset=options["reset_samples"],
        )
        if not options["skip_support_content"]:
            call_command("seed_support_content", updated_by=users["demo_admin"].username)

        if not options["skip_copy"]:
            copied_to = self._copy_database(options["prototype_file"])
            self.stdout.write(self.style.SUCCESS(f"Prototype database written to {copied_to}"))

        self.stdout.write(
            self.style.SUCCESS(
                "Demo logins: "
                "demo_admin / DemoAdmin123!, "
                "demo_worker / DemoUser123!, "
                "demo_referrer / DemoUser123!, "
                "demo_locked / DemoUser123!"
            )
        )

    @transaction.atomic
    def _ensure_demo_users(self):
        User = get_user_model()
        admin = self._upsert_user(
            User,
            username="demo_admin",
            email="demo.admin@example.com",
            phone_number="254700000001",
            password=DEMO_PASSWORDS["demo_admin"],
            is_staff=True,
            is_superuser=True,
            status=User.AccountStatus.ACTIVE,
            activation_status=User.ActivationStatus.ACTIVATED,
        )
        referrer = self._upsert_user(
            User,
            username="demo_referrer",
            email="demo.referrer@example.com",
            phone_number="254700000002",
            password=DEMO_PASSWORDS["demo_referrer"],
            referred_by=admin,
            status=User.AccountStatus.ACTIVE,
            activation_status=User.ActivationStatus.ACTIVATED,
        )
        worker = self._upsert_user(
            User,
            username="demo_worker",
            email="demo.worker@example.com",
            phone_number="254700000003",
            password=DEMO_PASSWORDS["demo_worker"],
            referred_by=referrer,
            status=User.AccountStatus.ACTIVE,
            activation_status=User.ActivationStatus.ACTIVATED,
        )
        locked = self._upsert_user(
            User,
            username="demo_locked",
            email="demo.locked@example.com",
            phone_number="254700000004",
            password=DEMO_PASSWORDS["demo_locked"],
            referred_by=referrer,
            status=User.AccountStatus.LOCKED,
            activation_status=User.ActivationStatus.NOT_ACTIVATED,
        )
        return {
            "demo_admin": admin,
            "demo_referrer": referrer,
            "demo_worker": worker,
            "demo_locked": locked,
        }

    def _upsert_user(
        self,
        User,
        *,
        username,
        email,
        phone_number,
        password,
        referred_by=None,
        is_staff=False,
        is_superuser=False,
        status,
        activation_status,
    ):
        user, _ = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "phone_number": phone_number,
                "country": "Kenya",
                "is_staff": is_staff,
                "is_superuser": is_superuser,
                "status": status,
                "activation_status": activation_status,
                "referred_by": referred_by,
            },
        )
        user.email = email
        user.phone_number = phone_number
        user.country = "Kenya"
        user.is_staff = is_staff
        user.is_superuser = is_superuser
        user.status = status
        user.activation_status = activation_status
        if referred_by:
            user.referred_by = referred_by
        user.set_password(password)
        user.save()
        return user

    def _ensure_demo_finance_settings(self, admin):
        finance_settings = FinanceSettings.load()
        finance_settings.activation_fee = Decimal("185.00")
        finance_settings.activation_withdrawable_amount = Decimal("50.00")
        finance_settings.referral_bonus_amount = Decimal("75.00")
        finance_settings.minimum_withdrawal_amount = Decimal("300.00")
        finance_settings.maximum_daily_withdrawal_per_user = Decimal("10000.00")
        finance_settings.reserve_ratio_target = Decimal("1.10")
        finance_settings.deposit_enabled = True
        finance_settings.payout_enabled = False
        finance_settings.job_claims_enabled = True
        finance_settings.updated_by = admin
        finance_settings.save()

    def _ensure_demo_balances(self, users):
        balances = {
            "demo_referrer": Decimal("850.00"),
            "demo_worker": Decimal("620.00"),
            "demo_locked": Decimal("0.00"),
        }
        for username, target_balance in balances.items():
            user = users[username]
            wallet = get_wallet(user)
            if wallet.available_balance >= target_balance or target_balance <= 0:
                continue
            amount = target_balance - wallet.available_balance
            post_ledger_transaction(
                user=user,
                amount=amount,
                transaction_type=LedgerTransaction.TransactionType.ADMIN_ADJUSTMENT,
                direction=LedgerTransaction.Direction.CREDIT,
                balance_bucket=LedgerTransaction.BalanceBucket.AVAILABLE,
                description="Prototype opening balance",
                idempotency_key=f"prototype-opening-balance-{username}-{target_balance}",
                source_app="core",
                source_model="prepare_prototype_database",
                source_id=username,
                created_by=users["demo_admin"],
            )

    def _copy_database(self, prototype_file):
        engine = connection.settings_dict.get("ENGINE", "")
        if engine != "django.db.backends.sqlite3":
            raise CommandError("The prototype bundle can only be copied from a SQLite database.")

        source = Path(connection.settings_dict["NAME"])
        if not source.exists():
            raise CommandError(f"SQLite database does not exist: {source}")

        destination = Path(settings.BASE_DIR) / prototype_file
        if source.resolve() == destination.resolve():
            return destination

        shutil.copyfile(source, destination)
        return destination
