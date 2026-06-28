from django.core.management.base import BaseCommand

from referrals.services import release_due_referral_bonuses


class Command(BaseCommand):
    help = "Release due referral bonuses into available wallet balances."

    def handle(self, *args, **options):
        released = release_due_referral_bonuses()
        self.stdout.write(self.style.SUCCESS(f"Released {released} referral bonus(es)."))
