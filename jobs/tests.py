from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.services import get_finance_settings
from wallets.services import get_wallet
from .models import Job, JobCategory, JobClaim, JobSubmission
from .services import approve_submission, claim_job, reject_submission, submit_job_proof


User = get_user_model()


class JobMarketplaceTests(TestCase):
    def setUp(self):
        self.referrer = User.objects.create_user(
            username="jobreferrer",
            email="jobreferrer@example.com",
            phone_number="254700111110",
            password="StrongPass123!",
        )
        self.user = User.objects.create_user(
            username="jobuser",
            email="jobuser@example.com",
            phone_number="254711111111",
            password="StrongPass123!",
            referred_by=self.referrer,
            status=User.AccountStatus.ACTIVE,
            activation_status=User.ActivationStatus.ACTIVATED,
        )
        self.admin = User.objects.create_user(
            username="jobadmin",
            email="jobadmin@example.com",
            phone_number="254722222222",
            password="StrongPass123!",
            is_staff=True,
            status=User.AccountStatus.ACTIVE,
            activation_status=User.ActivationStatus.ACTIVATED,
        )
        self.category = JobCategory.objects.create(name="Surveys", slug="surveys")
        self.job = Job.objects.create(
            category=self.category,
            title="Customer research survey",
            slug="customer-research-survey",
            job_type=Job.JobType.SURVEY,
            description="Answer a short customer research survey.",
            instructions="Complete the survey and paste the confirmation text.",
            reward_amount=Decimal("80.00"),
            worker_limit=2,
            status=Job.Status.PUBLISHED,
            proof_type=Job.ProofType.TEXT,
            starts_at=timezone.now(),
            created_by=self.admin,
        )

    def test_job_list_renders_open_jobs(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("job_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Customer research survey")

    def test_locked_user_cannot_claim_job(self):
        locked_user = User.objects.create_user(
            username="lockedjob",
            email="lockedjob@example.com",
            phone_number="254733333333",
            password="StrongPass123!",
        )

        with self.assertRaises(ValidationError):
            claim_job(job=self.job, user=locked_user)

    def test_disabled_job_claims_block_active_users(self):
        settings_obj = get_finance_settings()
        settings_obj.job_claims_enabled = False
        settings_obj.save(update_fields=["job_claims_enabled", "updated_at"])

        with self.assertRaisesMessage(
            ValidationError,
            "Jobs are not available at the moment but will be available once the client has approved them.",
        ):
            claim_job(job=self.job, user=self.user)

    def test_disabled_job_claims_still_asks_locked_users_to_activate_first(self):
        settings_obj = get_finance_settings()
        settings_obj.job_claims_enabled = False
        settings_obj.save(update_fields=["job_claims_enabled", "updated_at"])
        locked_user = User.objects.create_user(
            username="disabledlockedjob",
            email="disabledlockedjob@example.com",
            phone_number="254733333334",
            password="StrongPass123!",
            referred_by=self.referrer,
        )

        with self.assertRaisesMessage(ValidationError, "Activate your account before claiming jobs."):
            claim_job(job=self.job, user=locked_user)

    def test_disabled_job_claims_message_shows_on_claim_click(self):
        settings_obj = get_finance_settings()
        settings_obj.job_claims_enabled = False
        settings_obj.save(update_fields=["job_claims_enabled", "updated_at"])
        self.client.force_login(self.user)

        response = self.client.post(reverse("claim_job", kwargs={"slug": self.job.slug}), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Jobs are not available at the moment but will be available once the client has approved them.",
        )

    def test_claim_job_increments_count_and_marks_full(self):
        self.job.worker_limit = 1
        self.job.save(update_fields=["worker_limit"])

        claim = claim_job(job=self.job, user=self.user)

        self.job.refresh_from_db()
        self.assertEqual(claim.status, JobClaim.Status.CLAIMED)
        self.assertEqual(self.job.claims_count, 1)
        self.assertEqual(self.job.status, Job.Status.FULL)

    def test_submit_and_approve_job_posts_reward(self):
        claim = claim_job(job=self.job, user=self.user)
        submission = submit_job_proof(claim=claim, text_answer="Completed confirmation ABC123")

        approved, created = approve_submission(submission=submission, reviewer=self.admin)

        wallet = get_wallet(self.user)
        submission.refresh_from_db()
        self.job.refresh_from_db()
        self.assertTrue(created)
        self.assertEqual(approved.status, JobClaim.Status.APPROVED)
        self.assertEqual(submission.ledger_transaction.amount, Decimal("80.00"))
        self.assertEqual(wallet.available_balance, Decimal("80.00"))
        self.assertEqual(wallet.total_earned, Decimal("80.00"))
        self.assertEqual(self.job.pending_count, 0)
        self.assertEqual(self.job.approved_count, 1)

    def test_reject_submission_records_reason_without_reward(self):
        claim = claim_job(job=self.job, user=self.user)
        submission = submit_job_proof(claim=claim, text_answer="Incomplete answer")

        reject_submission(submission=submission, reviewer=self.admin, reason="Missing confirmation code")

        submission.refresh_from_db()
        wallet = get_wallet(self.user)
        self.job.refresh_from_db()
        self.assertEqual(submission.status, JobClaim.Status.REJECTED)
        self.assertEqual(submission.rejection_reason, "Missing confirmation code")
        self.assertEqual(wallet.available_balance, Decimal("0.00"))
        self.assertEqual(self.job.pending_count, 0)
        self.assertEqual(self.job.rejected_count, 1)

    def test_review_queue_requires_staff_and_renders_for_admin(self):
        claim = claim_job(job=self.job, user=self.user)
        submit_job_proof(claim=claim, text_answer="Completed confirmation ABC123")
        self.client.force_login(self.admin)

        response = self.client.get(reverse("review_queue"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Customer research survey")

    def test_submit_view_creates_submission(self):
        claim = claim_job(job=self.job, user=self.user)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("submit_job", kwargs={"claim_id": claim.pk}),
            {"text_answer": "Completed confirmation ABC123", "proof_url": ""},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(JobSubmission.objects.filter(user=self.user).count(), 1)
