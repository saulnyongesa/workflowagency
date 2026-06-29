from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from core.services import get_finance_settings
from wallets.models import LedgerTransaction
from wallets.services import post_ledger_transaction
from .models import Job, JobClaim, JobSubmission


@transaction.atomic
def claim_job(*, job, user):
    job = Job.objects.select_for_update().get(pk=job.pk)
    settings_obj = get_finance_settings()
    if user.status != user.AccountStatus.ACTIVE:
        raise ValidationError("Activate your account before claiming jobs.")
    if not settings_obj.job_claims_enabled:
        raise ValidationError(
            "Jobs are not available at the moment but will be available once the client has approved them."
        )
    today_claims = JobClaim.objects.filter(user=user, claimed_at__date=timezone.localdate()).count()
    if today_claims >= settings_obj.max_claims_per_user_per_day:
        raise ValidationError("You have reached today's job claim limit.")
    if job.job_type == Job.JobType.WATCH_AD:
        ad_claims_today = JobClaim.objects.filter(
            user=user,
            job__job_type=Job.JobType.WATCH_AD,
            claimed_at__date=timezone.localdate(),
        ).count()
        if ad_claims_today >= settings_obj.max_ad_watch_rewards_per_day:
            raise ValidationError("You have reached today's ad watch reward limit.")
    if not job.is_open:
        raise ValidationError("This job is not open for new claims.")
    existing_claims = JobClaim.objects.filter(job=job, user=user).count()
    if existing_claims >= job.max_claims_per_user:
        raise ValidationError("You have already claimed this job.")

    expires_at = timezone.now() + timezone.timedelta(minutes=job.claim_expires_after_minutes)
    try:
        claim = JobClaim.objects.create(job=job, user=user, expires_at=expires_at)
    except IntegrityError as exc:
        raise ValidationError("You have already claimed this job.") from exc

    job.claims_count += 1
    if job.claims_count >= job.worker_limit:
        job.status = Job.Status.FULL
    job.save(update_fields=["claims_count", "status", "updated_at"])
    return claim


@transaction.atomic
def submit_job_proof(*, claim, text_answer="", proof_url="", proof_file=None):
    claim = JobClaim.objects.select_for_update().select_related("job", "user").get(pk=claim.pk)
    if claim.status not in {JobClaim.Status.CLAIMED, JobClaim.Status.REJECTED}:
        raise ValidationError("This claim cannot be submitted.")
    if claim.expires_at < timezone.now():
        claim.status = JobClaim.Status.EXPIRED
        claim.save(update_fields=["status"])
        raise ValidationError("This claim has expired.")

    job = claim.job
    if job.proof_type in {Job.ProofType.TEXT, Job.ProofType.TEXT_URL} and not text_answer.strip():
        raise ValidationError("Text proof is required.")
    if job.proof_type in {Job.ProofType.URL, Job.ProofType.TEXT_URL} and not proof_url.strip():
        raise ValidationError("Proof URL is required.")
    if job.proof_type == Job.ProofType.FILE and not proof_file:
        raise ValidationError("Proof file is required.")

    submission, _ = JobSubmission.objects.update_or_create(
        claim=claim,
        defaults={
            "user": claim.user,
            "text_answer": text_answer,
            "proof_url": proof_url,
            "proof_file": proof_file or "",
            "status": JobClaim.Status.SUBMITTED,
            "rejection_reason": "",
        },
    )
    claim.status = JobClaim.Status.SUBMITTED
    claim.submitted_at = timezone.now()
    claim.save(update_fields=["status", "submitted_at"])
    job.pending_count += 1
    job.save(update_fields=["pending_count", "updated_at"])

    settings_obj = get_finance_settings()
    should_auto_approve = (
        job.review_mode == Job.ReviewMode.AUTO
        or (
            settings_obj.auto_approve_small_jobs
            and job.reward_amount <= settings_obj.auto_approve_job_reward_limit
        )
    )
    if should_auto_approve:
        approve_submission(submission=submission, reviewer=None)
        submission.refresh_from_db()
    return submission


@transaction.atomic
def approve_submission(*, submission, reviewer):
    submission = JobSubmission.objects.select_for_update().select_related("claim__job", "user").get(pk=submission.pk)
    if submission.status == JobClaim.Status.APPROVED:
        return submission, False
    if submission.status not in {JobClaim.Status.SUBMITTED, JobClaim.Status.REJECTED}:
        raise ValidationError("Only submitted jobs can be approved.")

    job = submission.claim.job
    ledger, _ = post_ledger_transaction(
        user=submission.user,
        amount=job.reward_amount,
        transaction_type=LedgerTransaction.TransactionType.JOB_REWARD_APPROVED,
        direction=LedgerTransaction.Direction.CREDIT,
        balance_bucket=LedgerTransaction.BalanceBucket.AVAILABLE,
        description=f"Approved reward for {job.title}",
        idempotency_key=f"job-submission-reward-{submission.pk}",
        source_app="jobs",
        source_model="JobSubmission",
        source_id=str(submission.pk),
        created_by=reviewer,
    )
    submission.status = JobClaim.Status.APPROVED
    submission.ledger_transaction = ledger
    submission.reviewed_by = reviewer
    submission.reviewed_at = timezone.now()
    submission.rejection_reason = ""
    submission.save(
        update_fields=[
            "status",
            "ledger_transaction",
            "reviewed_by",
            "reviewed_at",
            "rejection_reason",
            "updated_at",
        ]
    )
    claim = submission.claim
    claim.status = JobClaim.Status.APPROVED
    claim.reviewed_at = submission.reviewed_at
    claim.save(update_fields=["status", "reviewed_at"])
    if job.pending_count:
        job.pending_count -= 1
    job.approved_count += 1
    job.save(update_fields=["pending_count", "approved_count", "updated_at"])
    return submission, True


@transaction.atomic
def reject_submission(*, submission, reviewer, reason):
    submission = JobSubmission.objects.select_for_update().select_related("claim__job").get(pk=submission.pk)
    if submission.status == JobClaim.Status.APPROVED:
        raise ValidationError("Approved submissions cannot be rejected.")
    if not reason.strip():
        raise ValidationError("Rejection reason is required.")

    job = submission.claim.job
    submission.status = JobClaim.Status.REJECTED
    submission.reviewed_by = reviewer
    submission.reviewed_at = timezone.now()
    submission.rejection_reason = reason.strip()
    submission.save(update_fields=["status", "reviewed_by", "reviewed_at", "rejection_reason", "updated_at"])
    claim = submission.claim
    claim.status = JobClaim.Status.REJECTED
    claim.reviewed_at = submission.reviewed_at
    claim.save(update_fields=["status", "reviewed_at"])
    if job.pending_count:
        job.pending_count -= 1
    job.rejected_count += 1
    job.save(update_fields=["pending_count", "rejected_count", "updated_at"])
    return submission


def clone_job_as_new(*, job, created_by=None, worker_limit=None):
    clone = Job.objects.create(
        category=job.category,
        title=f"{job.title} (New)",
        slug=f"{job.slug}-{timezone.now().strftime('%Y%m%d%H%M%S')}",
        job_type=job.job_type,
        content_format=job.content_format,
        description=job.description,
        instructions=job.instructions,
        content_body=job.content_body,
        banner_image=job.banner_image,
        content_file=job.content_file,
        content_url=job.content_url,
        estimated_minutes=job.estimated_minutes,
        reward_amount=job.reward_amount,
        worker_limit=worker_limit or job.worker_limit,
        status=Job.Status.DRAFT,
        review_mode=job.review_mode,
        proof_type=job.proof_type,
        starts_at=timezone.now(),
        ends_at=job.ends_at,
        claim_expires_after_minutes=job.claim_expires_after_minutes,
        max_claims_per_user=job.max_claims_per_user,
        created_by=created_by,
        cloned_from=job,
    )
    return clone
