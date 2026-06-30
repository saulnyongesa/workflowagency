from decimal import Decimal

from django.core.management.base import BaseCommand

from jobs.models import ChatMessage, ChatProfile, ChatThread


CHAT_PROFILES = [
    {
        "display_name": "Emily Carter",
        "country": "United Kingdom",
        "headline": "Friendly conversation partner practicing casual English and travel stories.",
        "bio": "Emily enjoys short, respectful conversations about daily life, hobbies, books, travel, and culture.",
        "topic_prompt": "Start with a friendly greeting and ask about her favorite travel memory.",
        "avatar_initials": "EC",
        "rate_per_message": Decimal("12.00"),
        "sort_order": 10,
    },
    {
        "display_name": "Michael Brooks",
        "country": "United States",
        "headline": "Research-style chat partner interested in technology and online work.",
        "bio": "Michael represents a client research participant for testing paid conversation tasks. Keep the chat polite, clear, and focused on technology or remote work topics.",
        "topic_prompt": "Ask what kind of online tools make remote work easier.",
        "avatar_initials": "MB",
        "rate_per_message": Decimal("15.00"),
        "sort_order": 20,
    },
    {
        "display_name": "Sofia Martinez",
        "country": "Spain",
        "headline": "Beginner Swahili learner looking for simple greetings and pronunciation help.",
        "bio": "Sofia is learning beginner Swahili and wants simple greetings, pronunciation help, and short everyday phrases.",
        "topic_prompt": "Teach one simple Swahili greeting and explain when to use it.",
        "avatar_initials": "SM",
        "rate_per_message": Decimal("18.00"),
        "sort_order": 30,
    },
    {
        "display_name": "Jonas Weber",
        "country": "Germany",
        "headline": "Product feedback chat partner who asks about app usability and clarity.",
        "bio": "Jonas likes structured conversations about mobile app usability, product clarity, and practical feature feedback.",
        "topic_prompt": "Ask which mobile app feature he would like to test first.",
        "avatar_initials": "JW",
        "rate_per_message": Decimal("14.00"),
        "sort_order": 40,
    },
]


class Command(BaseCommand):
    help = "Seed international chat partners for the chat feature."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete seeded profiles before recreating.")

    def handle(self, *args, **options):
        names = [profile["display_name"] for profile in CHAT_PROFILES]
        if options["reset"]:
            profiles = ChatProfile.objects.filter(display_name__in=names)
            threads = ChatThread.objects.filter(profile__in=profiles)
            ChatMessage.objects.filter(thread__in=threads).delete()
            threads.delete()
            profiles.delete()

        created_count = 0
        for profile in CHAT_PROFILES:
            _, created = ChatProfile.objects.update_or_create(
                display_name=profile["display_name"],
                defaults={
                    **profile,
                    "is_active": True,
                },
            )
            created_count += int(created)

        self.stdout.write(
            self.style.SUCCESS(f"Chat profiles ready: {len(CHAT_PROFILES)} profiles ({created_count} new).")
        )
