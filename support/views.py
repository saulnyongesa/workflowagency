from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import StaffTicketUpdateForm, SupportTicketForm, SupportTicketReplyForm
from .models import Announcement, FAQ, PolicyPage, SupportTicket, SupportTicketReply


def _live_announcements(user):
    now = timezone.now()
    announcements = Announcement.objects.filter(is_published=True, starts_at__lte=now).filter(
        Q(ends_at__isnull=True) | Q(ends_at__gte=now)
    )
    if user.is_staff:
        return announcements[:5]
    if getattr(user, "status", "") == user.AccountStatus.ACTIVE:
        return announcements.exclude(audience=Announcement.Audience.STAFF)[:5]
    return announcements.filter(audience=Announcement.Audience.ALL).distinct()[:5]


@login_required
def support_center(request):
    faqs = FAQ.objects.filter(is_published=True)[:8]
    policies = PolicyPage.objects.filter(is_published=True)[:6]
    tickets = request.user.support_tickets.all()[:5]
    return render(
        request,
        "support/center.html",
        {
            "announcements": _live_announcements(request.user),
            "faqs": faqs,
            "policies": policies,
            "tickets": tickets,
        },
    )


@login_required
def support_ticket_list(request):
    tickets = request.user.support_tickets.all()
    return render(request, "support/ticket_list.html", {"tickets": tickets})


@login_required
def support_ticket_create(request):
    form = SupportTicketForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        ticket = form.save(commit=False)
        ticket.user = request.user
        ticket.status = SupportTicket.Status.OPEN
        ticket.save()
        SupportTicketReply.objects.create(
            ticket=ticket,
            sender=request.user,
            message=form.cleaned_data["message"],
            is_staff_reply=request.user.is_staff,
        )
        messages.success(request, "Support ticket created.")
        return redirect("support_ticket_detail", pk=ticket.pk)
    return render(request, "support/ticket_form.html", {"form": form})


@login_required
def support_ticket_detail(request, pk):
    ticket = get_object_or_404(
        SupportTicket.objects.select_related("user", "assigned_to").prefetch_related("replies", "replies__sender"),
        pk=pk,
    )
    if ticket.user != request.user and not request.user.is_staff:
        return redirect("support_ticket_list")

    reply_form = SupportTicketReplyForm()
    staff_form = StaffTicketUpdateForm(instance=ticket) if request.user.is_staff else None

    if request.method == "POST" and request.POST.get("action") == "reply":
        reply_form = SupportTicketReplyForm(request.POST)
        if reply_form.is_valid():
            reply = reply_form.save(commit=False)
            reply.ticket = ticket
            reply.sender = request.user
            reply.is_staff_reply = request.user.is_staff
            reply.save()
            if request.user.is_staff:
                ticket.status = SupportTicket.Status.WAITING_USER
            elif ticket.status in {SupportTicket.Status.RESOLVED, SupportTicket.Status.CLOSED}:
                ticket.status = SupportTicket.Status.WAITING_STAFF
                ticket.resolved_at = None
            else:
                ticket.status = SupportTicket.Status.WAITING_STAFF
            ticket.save(update_fields=["status", "resolved_at", "updated_at"])
            messages.success(request, "Reply added.")
            return redirect("support_ticket_detail", pk=ticket.pk)

    if request.method == "POST" and request.POST.get("action") == "staff_update" and request.user.is_staff:
        staff_form = StaffTicketUpdateForm(request.POST, instance=ticket)
        if staff_form.is_valid():
            updated_ticket = staff_form.save(commit=False)
            if updated_ticket.status in {SupportTicket.Status.RESOLVED, SupportTicket.Status.CLOSED}:
                updated_ticket.resolved_at = updated_ticket.resolved_at or timezone.now()
            else:
                updated_ticket.resolved_at = None
            updated_ticket.save()
            messages.success(request, "Ticket updated.")
            return redirect("support_ticket_detail", pk=ticket.pk)

    return render(
        request,
        "support/ticket_detail.html",
        {"ticket": ticket, "reply_form": reply_form, "staff_form": staff_form},
    )


@staff_member_required
def support_ticket_queue(request):
    status = request.GET.get("status", "").strip()
    tickets = SupportTicket.objects.select_related("user", "assigned_to")
    if status:
        tickets = tickets.filter(status=status)
    else:
        tickets = tickets.exclude(status__in=[SupportTicket.Status.RESOLVED, SupportTicket.Status.CLOSED])
    return render(
        request,
        "support/ticket_queue.html",
        {"tickets": tickets, "statuses": SupportTicket.Status.choices, "selected_status": status},
    )


def policy_list(request):
    policies = PolicyPage.objects.filter(is_published=True)
    return render(request, "support/policy_list.html", {"policies": policies})


def policy_detail(request, slug):
    policy = get_object_or_404(PolicyPage, slug=slug, is_published=True)
    return render(request, "support/policy_detail.html", {"policy": policy})


def faq_list(request):
    faqs = FAQ.objects.filter(is_published=True)
    return render(request, "support/faq_list.html", {"faqs": faqs})
