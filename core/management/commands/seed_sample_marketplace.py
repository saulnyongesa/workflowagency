from decimal import Decimal
from random import Random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from jobs.models import Job, JobCategory, JobClaim, JobSubmission
from products.models import Product, ProductCategory, ProductCommission, ProductPurchase


SAMPLE_JOB_PREFIX = "sample-job-"
SAMPLE_SURVEY_PREFIX = "sample-survey-"
SAMPLE_PRODUCT_PREFIX = "sample-product-"


JOB_CATEGORIES = [
    ("app-testing", "App Testing", "#0b5fff"),
    ("ad-watch", "Watch Ads", "#f59e0b"),
    ("website-feedback", "Website Feedback", "#14b8a6"),
    ("data-entry", "Data Entry", "#6366f1"),
    ("transcription", "Transcription", "#22c55e"),
    ("translation", "Translation", "#ef4444"),
    ("product-review", "Product Review", "#8b5cf6"),
    ("paid-chat", "Paid Chat", "#06b6d4"),
    ("swahili-teaching", "Teach Swahili", "#10b981"),
    ("ai-training", "AI Training", "#7c3aed"),
    ("affiliate-tasks", "Affiliate Tasks", "#f97316"),
]

PRODUCT_CATEGORIES = [
    ("stories", "Stories", "Short paid reading and creative story resources."),
    ("videos", "Videos", "Training, entertainment, and skill videos."),
    ("articles", "Articles", "Research, news, and learning articles."),
    ("guides", "Guides", "Practical guides and how-to resources."),
    ("templates", "Templates", "Reusable templates and digital tools."),
    ("courses", "Courses", "Learning packs and mini courses."),
    ("tools", "Tools", "Digital utilities and workflow resources."),
]

SURVEY_TOPICS = [
    "Mobile Money Usage",
    "Online Shopping Experience",
    "AI Tools at Work",
    "Campus Budget Habits",
    "Home Internet Quality",
    "Food Delivery Feedback",
    "Gaming and Rewards",
    "Small Business Payments",
    "Digital Learning Needs",
    "Savings and Loans Awareness",
]

JOB_TITLE_PATTERNS = {
    Job.JobType.WATCH_AD: [
        "Watch a Fintech Explainer Video",
        "Review a Mobile App Promotion",
        "Watch a Short Product Launch Ad",
        "Rate a Savings Campaign Video",
    ],
    Job.JobType.APP_TESTING: [
        "Test a Wallet App Signup Flow",
        "Try a Game Level and Report Issues",
        "Check a Delivery App Checkout Flow",
        "Test a Learning App Onboarding Screen",
    ],
    Job.JobType.WEBSITE_FEEDBACK: [
        "Review a Landing Page Navigation Flow",
        "Check a Product Page on Mobile",
        "Give Feedback on a Course Signup Page",
        "Audit a Checkout Page for Clarity",
    ],
    Job.JobType.DATA_ENTRY: [
        "Tag Product Listings From a Spreadsheet",
        "Clean Customer Feedback Categories",
        "Match Short Leads to Business Types",
        "Verify Contact Records for a Campaign",
    ],
    Job.JobType.TRANSCRIPTION: [
        "Transcribe a Two Minute Customer Audio",
        "Convert a Short Interview Clip to Text",
        "Transcribe a Swahili-English Voice Note",
        "Capture Key Points From a Training Clip",
    ],
    Job.JobType.TRANSLATION: [
        "Translate Product Copy From English to Swahili",
        "Localize App Notification Text",
        "Translate a Short Support Reply",
        "Rewrite a Promo Message for Kenyan Users",
    ],
    Job.JobType.PRODUCT_REVIEW: [
        "Review a Digital Guide Preview",
        "Rate a Template Pack After Download",
        "Give Product Feedback on a Course Outline",
        "Review a Short Story Reading Pack",
    ],
    Job.JobType.CHAT_SESSION: [
        "Join a Fifteen Minute English Practice Chat",
        "Hold a Product Feedback Chat Session",
        "Join a Customer Research Conversation",
        "Complete a Guided Chat Interview",
    ],
    Job.JobType.SWAHILI_TEACHING: [
        "Teach Beginner Swahili Greetings",
        "Practice Swahili Travel Phrases",
        "Record Simple Swahili Pronunciation Notes",
        "Guide a Short Swahili Conversation",
    ],
    Job.JobType.AI_TRAINING: [
        "Compare Two AI Assistant Answers",
        "Label Helpful and Unhelpful AI Replies",
        "Rewrite a Prompt for Better AI Output",
        "Rate AI Responses for Safety and Clarity",
    ],
    Job.JobType.PRODUCT_AFFILIATE: [
        "Share a Course Offer With a Tracked Link",
        "Promote a Template Pack to Your Network",
        "Share a Digital Guide With Proof",
        "Invite Buyers to a Skills Resource",
    ],
}

JOB_DESCRIPTIONS = {
    Job.JobType.WATCH_AD: "Watch the assigned video, note the key message, and submit the requested feedback for review.",
    Job.JobType.APP_TESTING: "Use your phone to complete the assigned flow and report any confusing steps, errors, or delays.",
    Job.JobType.WEBSITE_FEEDBACK: "Open the page on mobile, follow the required steps, and explain what felt clear or difficult.",
    Job.JobType.DATA_ENTRY: "Process the provided records carefully and submit the completed confirmation or reference link.",
    Job.JobType.TRANSCRIPTION: "Listen to the short audio or video clip and submit clean, readable text with speaker notes where needed.",
    Job.JobType.TRANSLATION: "Translate the assigned short text naturally while keeping the meaning, tone, and call to action intact.",
    Job.JobType.PRODUCT_REVIEW: "Review the product preview, check the stated value, and submit useful buyer-focused feedback.",
    Job.JobType.CHAT_SESSION: "Attend the timed chat session, follow the conversation brief, and submit the session confirmation.",
    Job.JobType.SWAHILI_TEACHING: "Help an international learner practice simple Swahili phrases and submit a short session summary.",
    Job.JobType.AI_TRAINING: "Review AI-generated content, label quality issues, and submit the required evaluation notes.",
    Job.JobType.PRODUCT_AFFILIATE: "Share the approved offer using the provided link and submit proof of the completed promotion.",
}

JOB_INSTRUCTIONS = {
    Job.JobType.WATCH_AD: "Watch the full media item, answer the attention question, then submit the completion code or short feedback.",
    Job.JobType.APP_TESTING: "Install or open the test link, complete the listed screens, then submit screenshots or a short issue report.",
    Job.JobType.WEBSITE_FEEDBACK: "Use a mobile browser, complete the assigned journey, then submit the URL and your feedback notes.",
    Job.JobType.DATA_ENTRY: "Follow the field instructions exactly, avoid duplicates, and submit the finished sheet or confirmation text.",
    Job.JobType.TRANSCRIPTION: "Transcribe only what you hear, mark unclear sections, and submit the final text before the claim expires.",
    Job.JobType.TRANSLATION: "Keep the translation simple and natural, preserve product names, and submit both source and final text.",
    Job.JobType.PRODUCT_REVIEW: "Open the product preview, check the headline and value promise, then submit practical improvement notes.",
    Job.JobType.CHAT_SESSION: "Join at the scheduled time, stay for the full session, and submit the session reference after completion.",
    Job.JobType.SWAHILI_TEACHING: "Follow the lesson prompt, keep the language simple, and submit the learner topic plus your teaching notes.",
    Job.JobType.AI_TRAINING: "Read both AI outputs carefully, apply the rating guide, and submit concise reasons for your choices.",
    Job.JobType.PRODUCT_AFFILIATE: "Use only the approved message, share through one allowed channel, and submit a proof link or screenshot note.",
}

PRODUCT_TITLE_PATTERNS = {
    Product.ContentFormat.GUIDE: [
        "Remote Work Starter Guide",
        "M-Pesa Budgeting Guide",
        "Beginner Affiliate Sales Guide",
        "Mobile Survey Earning Guide",
    ],
    Product.ContentFormat.STORY: [
        "Nairobi Hustle Story Pack",
        "Campus Life Short Reads",
        "Village to City Story Bundle",
        "Digital Hustle Fiction Collection",
    ],
    Product.ContentFormat.ARTICLE: [
        "AI Tools for Online Workers",
        "Mobile Money Safety Brief",
        "Freelance Profile Improvement Article",
        "Side Income Research Digest",
    ],
    Product.ContentFormat.VIDEO: [
        "Canva Ad Design Mini Lesson",
        "Beginner Game Testing Walkthrough",
        "Phone Photography Product Demo",
        "Online Work Onboarding Video",
    ],
    Product.ContentFormat.TEMPLATE: [
        "Client Outreach Message Templates",
        "Survey Tracker Spreadsheet",
        "Affiliate Campaign Planner",
        "Simple CV and Bio Template Pack",
    ],
    Product.ContentFormat.FILE: [
        "Task Proof Checklist Pack",
        "Freelancer Profile Resource File",
        "Digital Product Launch Workbook",
        "Mobile QA Reporting Worksheet",
    ],
    Product.ContentFormat.LINK: [
        "Curated Remote Jobs Resource List",
        "Free Learning Links Collection",
        "Creator Tools Directory",
        "Verified Productivity Resource Board",
    ],
}

PRODUCT_SUMMARIES = {
    Product.ContentFormat.GUIDE: "A practical step-by-step guide for improving online earning skills and safer digital work habits.",
    Product.ContentFormat.STORY: "A short reading pack created for quick mobile reading, engagement tasks, and content promotions.",
    Product.ContentFormat.ARTICLE: "A focused article with practical insights for online work, digital safety, and mobile-first earning.",
    Product.ContentFormat.VIDEO: "A short training video designed for learners who want quick, phone-friendly skill lessons.",
    Product.ContentFormat.TEMPLATE: "A reusable template pack for tracking work, planning campaigns, and presenting yourself professionally.",
    Product.ContentFormat.FILE: "A downloadable resource file with checklists, worksheets, or reference material for online workers.",
    Product.ContentFormat.LINK: "A curated resource link collection for learning, productivity, and marketplace research.",
}


class Command(BaseCommand):
    help = "Seed sample jobs, survey jobs, and products for local demos."

    def add_arguments(self, parser):
        parser.add_argument("--jobs", type=int, default=5000, help="Target number of sample non-survey jobs.")
        parser.add_argument("--surveys", type=int, default=5000, help="Target number of sample survey jobs.")
        parser.add_argument("--products", type=int, default=5000, help="Target number of sample products.")
        parser.add_argument("--batch-size", type=int, default=1000, help="Bulk insert batch size.")
        parser.add_argument("--seed", type=int, default=20260629, help="Random seed for deterministic sample data.")
        parser.add_argument("--reset", action="store_true", help="Delete existing sample rows before seeding.")

    def handle(self, *args, **options):
        jobs_target = max(options["jobs"], 0)
        surveys_target = max(options["surveys"], 0)
        products_target = max(options["products"], 0)
        batch_size = max(options["batch_size"], 1)
        rng = Random(options["seed"])

        if options["reset"]:
            self._reset_samples()

        creator = self._creator()
        job_categories = self._job_categories()
        survey_category = self._survey_category()
        product_categories = self._product_categories()

        created_jobs = self._top_up_jobs(
            prefix=SAMPLE_JOB_PREFIX,
            target=jobs_target,
            batch_size=batch_size,
            rng=rng,
            creator=creator,
            categories=job_categories,
            survey=False,
        )
        created_surveys = self._top_up_jobs(
            prefix=SAMPLE_SURVEY_PREFIX,
            target=surveys_target,
            batch_size=batch_size,
            rng=rng,
            creator=creator,
            categories=[survey_category],
            survey=True,
        )
        created_products = self._top_up_products(
            target=products_target,
            batch_size=batch_size,
            rng=rng,
            creator=creator,
            categories=product_categories,
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Seed complete: "
                f"{created_jobs} jobs, {created_surveys} surveys, {created_products} products created."
            )
        )

    def _creator(self):
        User = get_user_model()
        return User.objects.filter(is_staff=True).first() or User.objects.first()

    def _reset_samples(self):
        sample_jobs = Job.objects.filter(Q(slug__startswith=SAMPLE_JOB_PREFIX) | Q(slug__startswith=SAMPLE_SURVEY_PREFIX))
        sample_products = Product.objects.filter(slug__startswith=SAMPLE_PRODUCT_PREFIX)
        sample_purchases = ProductPurchase.objects.filter(product__in=sample_products)
        sample_claims = JobClaim.objects.filter(job__in=sample_jobs)
        with transaction.atomic():
            deleted_commissions = ProductCommission.objects.filter(purchase__in=sample_purchases).delete()[0]
            deleted_purchases = sample_purchases.delete()[0]
            deleted_submissions = JobSubmission.objects.filter(claim__in=sample_claims).delete()[0]
            deleted_claims = sample_claims.delete()[0]
            deleted_products = sample_products.delete()[0]
            deleted_jobs = sample_jobs.delete()[0]
        self.stdout.write(
            "Deleted sample data: "
            f"{deleted_jobs} job rows, {deleted_claims} claims, {deleted_submissions} submissions, "
            f"{deleted_products} product rows, {deleted_purchases} purchases, {deleted_commissions} commissions."
        )

    def _job_categories(self):
        categories = []
        for sort_order, (slug, name, color) in enumerate(JOB_CATEGORIES, start=10):
            category, _ = JobCategory.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "icon": "briefcase-business",
                    "color": color,
                    "sort_order": sort_order,
                },
            )
            categories.append(category)
        return categories

    def _survey_category(self):
        category, _ = JobCategory.objects.get_or_create(
            slug="surveys",
            defaults={
                "name": "Surveys",
                "icon": "clipboard-list",
                "color": "#0ea5e9",
                "sort_order": 1,
            },
        )
        return category

    def _product_categories(self):
        categories = []
        for sort_order, (slug, name, description) in enumerate(PRODUCT_CATEGORIES, start=1):
            category, _ = ProductCategory.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "description": description,
                    "sort_order": sort_order,
                },
            )
            categories.append(category)
        return categories

    def _top_up_jobs(self, *, prefix, target, batch_size, rng, creator, categories, survey):
        existing_count = Job.objects.filter(slug__startswith=prefix).count()
        missing = max(target - existing_count, 0)
        if missing == 0:
            self.stdout.write(f"{prefix} already has {existing_count} rows. Nothing to add.")
            return 0

        now = timezone.now()
        existing_slugs = set(Job.objects.filter(slug__startswith=prefix).values_list("slug", flat=True))
        created = 0
        sequence = 1
        job_types = [
            Job.JobType.WATCH_AD,
            Job.JobType.APP_TESTING,
            Job.JobType.WEBSITE_FEEDBACK,
            Job.JobType.DATA_ENTRY,
            Job.JobType.TRANSCRIPTION,
            Job.JobType.TRANSLATION,
            Job.JobType.PRODUCT_REVIEW,
            Job.JobType.CHAT_SESSION,
            Job.JobType.SWAHILI_TEACHING,
            Job.JobType.AI_TRAINING,
            Job.JobType.PRODUCT_AFFILIATE,
        ]
        content_formats = [
            Job.ContentFormat.TASK,
            Job.ContentFormat.VIDEO,
            Job.ContentFormat.ARTICLE,
            Job.ContentFormat.FILE,
            Job.ContentFormat.EXTERNAL,
        ]

        while created < missing:
            batch = []
            while len(batch) < batch_size and created < missing:
                slug = f"{prefix}{sequence:06d}"
                display_sequence = sequence
                sequence += 1
                if slug in existing_slugs:
                    continue

                category = categories[0] if survey else rng.choice(categories)
                job_type = Job.JobType.SURVEY if survey else rng.choice(job_types)
                content_format = Job.ContentFormat.SURVEY if survey else rng.choice(content_formats)
                reward = Decimal(str(rng.choice([15, 20, 25, 35, 50, 75, 100, 150, 200, 350, 500])))
                worker_limit = rng.randint(30, 350)
                title = self._job_title(display_sequence, job_type, survey)
                batch.append(
                    Job(
                        category=category,
                        title=title,
                        slug=slug,
                        job_type=job_type,
                        content_format=content_format,
                        description=self._job_description(job_type, survey),
                        instructions=self._job_instructions(job_type, survey),
                        content_body=self._job_content_body(job_type, survey),
                        content_url=f"https://demo.workflowagency.local/tasks/{slug}",
                        estimated_minutes=rng.randint(3, 25),
                        reward_amount=reward,
                        worker_limit=worker_limit,
                        status=Job.Status.PUBLISHED,
                        review_mode=Job.ReviewMode.MANUAL,
                        proof_type=rng.choice([Job.ProofType.TEXT, Job.ProofType.URL, Job.ProofType.TEXT_URL]),
                        starts_at=now - timezone.timedelta(days=rng.randint(0, 10)),
                        ends_at=now + timezone.timedelta(days=rng.randint(30, 180)),
                        claim_expires_after_minutes=rng.choice([180, 360, 720, 1440]),
                        max_claims_per_user=1,
                        created_by=creator,
                    )
                )
                existing_slugs.add(slug)
                created += 1

            Job.objects.bulk_create(batch, batch_size=batch_size)
            self.stdout.write(f"Created {created}/{missing} rows for {prefix}")
        return created

    def _top_up_products(self, *, target, batch_size, rng, creator, categories):
        existing_count = Product.objects.filter(slug__startswith=SAMPLE_PRODUCT_PREFIX).count()
        missing = max(target - existing_count, 0)
        if missing == 0:
            self.stdout.write(f"{SAMPLE_PRODUCT_PREFIX} already has {existing_count} rows. Nothing to add.")
            return 0

        existing_slugs = set(Product.objects.filter(slug__startswith=SAMPLE_PRODUCT_PREFIX).values_list("slug", flat=True))
        created = 0
        sequence = 1
        content_formats = [
            Product.ContentFormat.GUIDE,
            Product.ContentFormat.STORY,
            Product.ContentFormat.ARTICLE,
            Product.ContentFormat.VIDEO,
            Product.ContentFormat.TEMPLATE,
            Product.ContentFormat.FILE,
            Product.ContentFormat.LINK,
        ]

        while created < missing:
            batch = []
            while len(batch) < batch_size and created < missing:
                slug = f"{SAMPLE_PRODUCT_PREFIX}{sequence:06d}"
                display_sequence = sequence
                sequence += 1
                if slug in existing_slugs:
                    continue

                content_format = rng.choice(content_formats)
                price = Decimal(str(rng.choice([0, 49, 99, 150, 250, 399, 500, 750, 999, 1500])))
                commission_type = rng.choice(
                    [Product.CommissionType.NONE, Product.CommissionType.FIXED, Product.CommissionType.PERCENT]
                )
                batch.append(
                    Product(
                        category=rng.choice(categories),
                        title=self._product_title(display_sequence, content_format),
                        slug=slug,
                        product_type=Product.ProductType.EXTERNAL_LINK,
                        content_format=content_format,
                        status=Product.Status.PUBLISHED,
                        summary=self._product_summary(content_format),
                        description=self._product_description(content_format),
                        price=price,
                        external_url=f"https://demo.workflowagency.local/products/{slug}",
                        stock_quantity=None,
                        commission_type=commission_type,
                        commission_amount=Decimal("25.00") if commission_type == Product.CommissionType.FIXED else Decimal("0.00"),
                        commission_percent=Decimal("8.00") if commission_type == Product.CommissionType.PERCENT else Decimal("0.00"),
                        commission_release_delay_hours=24,
                        created_by=creator,
                    )
                )
                existing_slugs.add(slug)
                created += 1

            Product.objects.bulk_create(batch, batch_size=batch_size)
            self.stdout.write(f"Created {created}/{missing} rows for {SAMPLE_PRODUCT_PREFIX}")
        return created

    def _job_title(self, sequence, job_type, survey):
        if survey:
            topic = SURVEY_TOPICS[sequence % len(SURVEY_TOPICS)]
            return f"{topic} Survey - Panel {sequence:06d}"
        titles = JOB_TITLE_PATTERNS.get(job_type, ["Complete a Verified Online Task"])
        return f"{titles[sequence % len(titles)]} - Batch {sequence:06d}"

    def _job_description(self, job_type, survey):
        if survey:
            return "Answer a short consumer research survey and submit the final confirmation code as proof."
        return JOB_DESCRIPTIONS.get(
            job_type,
            "Complete the assigned online task and submit clear proof for review.",
        )

    def _job_instructions(self, job_type, survey):
        if survey:
            return "Open the survey link, answer honestly, copy the completion code, and submit it as proof."
        return JOB_INSTRUCTIONS.get(
            job_type,
            "Read the task brief, complete every step, then submit the requested proof before the claim expires.",
        )

    def _job_content_body(self, job_type, survey):
        if survey:
            return (
                "The research team is collecting mobile-first responses from Kenyan users. "
                "Complete the survey in one sitting and do not submit duplicate answers."
            )
        return (
            f"This {Job.JobType(job_type).label.lower()} is available to a limited worker group. "
            "Claim only if you can finish it carefully and provide the requested proof."
        )

    def _product_title(self, sequence, content_format):
        titles = PRODUCT_TITLE_PATTERNS.get(content_format, ["Digital Resource Pack"])
        return f"{titles[sequence % len(titles)]} {sequence:06d}"

    def _product_summary(self, content_format):
        return PRODUCT_SUMMARIES.get(
            content_format,
            "A practical digital resource for mobile-first online workers.",
        )

    def _product_description(self, content_format):
        return (
            f"This {Product.ContentFormat(content_format).label.lower()} is packaged for quick mobile access. "
            "It includes a clear overview, practical steps, and delivery notes so buyers can use it immediately after purchase."
        )
