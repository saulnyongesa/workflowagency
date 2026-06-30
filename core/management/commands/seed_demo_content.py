from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from core.seed_content import DEFAULT_BULK_SEED_TARGETS, run_bulk_content_seed


class Command(BaseCommand):
    help = "Seed a large set of jobs, surveys, products, policies, FAQs, and chat profiles."

    def add_arguments(self, parser):
        parser.add_argument("--jobs", type=int, default=DEFAULT_BULK_SEED_TARGETS["jobs"])
        parser.add_argument("--surveys", type=int, default=DEFAULT_BULK_SEED_TARGETS["surveys"])
        parser.add_argument("--products", type=int, default=DEFAULT_BULK_SEED_TARGETS["products"])
        parser.add_argument("--batch-size", type=int, default=1000)
        parser.add_argument("--reset-marketplace", action="store_true", help="Delete generated marketplace rows first.")
        parser.add_argument("--actor", default="", help="Optional admin username to attach to status/audit records.")

    def handle(self, *args, **options):
        actor_id = None
        if options["actor"]:
            User = get_user_model()
            actor = User.objects.filter(username=options["actor"]).first()
            actor_id = actor.pk if actor else None
        run_bulk_content_seed(
            jobs=options["jobs"],
            surveys=options["surveys"],
            products=options["products"],
            batch_size=options["batch_size"],
            reset_marketplace=options["reset_marketplace"],
            actor_id=actor_id,
        )
        self.stdout.write(self.style.SUCCESS("Demo content seeding completed."))
