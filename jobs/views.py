from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.services import get_finance_settings
from .forms import ChatMessageForm, JobSubmissionForm, RejectionForm
from .models import ChatProfile, ChatThread, Job, JobCategory, JobClaim, JobSubmission
from .services import (
    approve_submission,
    claim_job,
    clone_job_as_new,
    reject_submission,
    send_chat_message,
    submit_job_proof,
)


@login_required
def job_list(request):
    now = timezone.now()
    jobs = (
        Job.objects.filter(status=Job.Status.PUBLISHED, starts_at__lte=now, claims_count__lt=F("worker_limit"))
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gte=now))
        .select_related("category")
    )
    category_slug = request.GET.get("category", "").strip()
    job_type = request.GET.get("type", "").strip()
    q = request.GET.get("q", "").strip()
    if category_slug:
        jobs = jobs.filter(category__slug=category_slug)
    if job_type:
        jobs = jobs.filter(job_type=job_type)
    if q:
        jobs = jobs.filter(title__icontains=q)
    categories = JobCategory.objects.filter(is_active=True)
    paginator = Paginator(jobs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))
    query_params = request.GET.copy()
    query_params.pop("page", None)
    return render(
        request,
        "jobs/job_list.html",
        {
            "jobs": page_obj.object_list,
            "page_obj": page_obj,
            "page_query": query_params.urlencode(),
            "categories": categories,
            "job_types": Job.JobType.choices,
            "selected_category": category_slug,
            "selected_type": job_type,
            "search_query": q,
        },
    )


@login_required
def job_detail(request, slug):
    job = get_object_or_404(Job.objects.select_related("category"), slug=slug)
    claim = JobClaim.objects.filter(job=job, user=request.user).first()
    submission = getattr(claim, "submission", None) if claim else None
    return render(request, "jobs/job_detail.html", {"job": job, "claim": claim, "submission": submission})


@login_required
@require_POST
def claim_job_view(request, slug):
    job = get_object_or_404(Job, slug=slug)
    try:
        claim = claim_job(job=job, user=request.user)
    except ValidationError as exc:
        messages.error(request, exc.messages[0] if hasattr(exc, "messages") else str(exc))
        return redirect("job_detail", slug=job.slug)
    messages.success(request, "Job claimed. Submit proof before the claim expires.")
    return redirect("submit_job", claim_id=claim.pk)


@login_required
def submit_job(request, claim_id):
    claim = get_object_or_404(JobClaim.objects.select_related("job", "user"), pk=claim_id, user=request.user)
    form = JobSubmissionForm(request.POST or None, request.FILES or None, job=claim.job)
    if request.method == "POST" and form.is_valid():
        try:
            submission = submit_job_proof(
                claim=claim,
                text_answer=form.cleaned_data.get("text_answer", ""),
                proof_url=form.cleaned_data.get("proof_url", ""),
                proof_file=form.cleaned_data.get("proof_file"),
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Job proof submitted.")
            return redirect("job_submission_detail", submission_id=submission.pk)
    return render(request, "jobs/submit_job.html", {"claim": claim, "form": form})


@login_required
def job_submission_detail(request, submission_id):
    submission = get_object_or_404(
        JobSubmission.objects.select_related("claim__job", "user", "ledger_transaction"),
        pk=submission_id,
    )
    if submission.user != request.user and not request.user.is_staff:
        return redirect("job_list")
    return render(request, "jobs/submission_detail.html", {"submission": submission})


@login_required
def my_jobs(request):
    claims = request.user.job_claims.select_related("job", "job__category").all()
    return render(request, "jobs/my_jobs.html", {"claims": claims})


@login_required
def chat_lobby(request):
    finance_settings = get_finance_settings()
    profiles = ChatProfile.objects.filter(is_active=True)
    recent_threads = request.user.chat_threads.select_related("profile")[:5]
    earning_tracks = [
        {
            "title": "Teach foreigners Swahili",
            "description": "Help international learners practice greetings, daily phrases, pronunciation, and simple conversations.",
            "url": f"{reverse('job_list')}?type={Job.JobType.SWAHILI_TEACHING}",
            "icon": "languages",
        },
        {
            "title": "Train AI systems",
            "description": "Label responses, compare answers, rewrite prompts, and improve AI assistant quality through structured tasks.",
            "url": f"{reverse('job_list')}?type={Job.JobType.AI_TRAINING}",
            "icon": "bot",
        },
    ]
    return render(
        request,
        "jobs/chat_lobby.html",
        {
            "profiles": profiles,
            "recent_threads": recent_threads,
            "finance_settings": finance_settings,
            "earning_tracks": earning_tracks,
        },
    )


@login_required
def chat_thread(request, profile_id):
    profile = get_object_or_404(ChatProfile, pk=profile_id, is_active=True)
    finance_settings = get_finance_settings()
    thread = (
        ChatThread.objects.filter(user=request.user, profile=profile)
        .prefetch_related("messages")
        .order_by("-last_message_at")
        .first()
    )
    form = ChatMessageForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            thread = send_chat_message(
                profile=profile,
                user=request.user,
                body=form.cleaned_data["body"],
            )
        except ValidationError as exc:
            form.add_error(None, exc.messages[0] if hasattr(exc, "messages") else str(exc))
        else:
            messages.info(request, f"{profile.display_name} is offline. We saved your message.")
            return redirect("chat_thread", profile_id=profile.pk)

    chat_messages = thread.messages.all() if thread else []
    return render(
        request,
        "jobs/chat_thread.html",
        {
            "profile": profile,
            "thread": thread,
            "chat_messages": chat_messages,
            "form": form,
            "finance_settings": finance_settings,
        },
    )


@staff_member_required
def review_queue(request):
    submissions = JobSubmission.objects.filter(status=JobClaim.Status.SUBMITTED).select_related("claim__job", "user")
    return render(request, "jobs/review_queue.html", {"submissions": submissions})


@staff_member_required
@require_POST
def approve_submission_view(request, submission_id):
    submission = get_object_or_404(JobSubmission, pk=submission_id)
    try:
        approve_submission(submission=submission, reviewer=request.user)
    except ValidationError as exc:
        messages.error(request, exc.messages[0] if hasattr(exc, "messages") else str(exc))
    else:
        messages.success(request, "Submission approved and reward posted.")
    return redirect("review_queue")


@staff_member_required
def reject_submission_view(request, submission_id):
    submission = get_object_or_404(JobSubmission.objects.select_related("claim__job", "user"), pk=submission_id)
    form = RejectionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            reject_submission(submission=submission, reviewer=request.user, reason=form.cleaned_data["reason"])
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Submission rejected.")
            return redirect("review_queue")
    return render(request, "jobs/reject_submission.html", {"submission": submission, "form": form})


@staff_member_required
@require_POST
def clone_job_view(request, job_id):
    job = get_object_or_404(Job, pk=job_id)
    clone = clone_job_as_new(job=job, created_by=request.user)
    messages.success(request, "Job cloned as a new draft.")
    return redirect("admin_job_edit", job_id=clone.pk)
