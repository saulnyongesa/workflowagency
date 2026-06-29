from django.core.management.base import BaseCommand

from products.services import release_due_product_commissions


class Command(BaseCommand):
    help = "Release due product commissions into referrer wallets."

    def handle(self, *args, **options):
        released = release_due_product_commissions()
        self.stdout.write(self.style.SUCCESS(f"Released {released} product commission(s)."))
