from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import FAQ, PolicyPage, SupportTicket, SupportTicketReply


User = get_user_model()


class SupportFlowTests(TestCase):
    def setUp(self):
        self.referrer = User.objects.create_user(
            username="supportreferrer",
            email="supportreferrer@example.com",
            phone_number="254722200000",
            password="StrongPass123!",
        )
        self.user = User.objects.create_user(
            username="supportuser",
            email="supportuser@example.com",
            phone_number="254722200001",
            password="StrongPass123!",
            referred_by=self.referrer,
        )
        self.staff = User.objects.create_user(
            username="supportstaff",
            email="supportstaff@example.com",
            phone_number="254722200002",
            password="StrongPass123!",
            is_staff=True,
        )
        self.policy = PolicyPage.objects.create(
            title="Withdrawal Policy",
            slug="withdrawal-policy",
            policy_type=PolicyPage.PolicyType.WITHDRAWAL,
            summary="Withdrawal rules.",
            body="Minimum withdrawals and review rules apply.",
        )
        FAQ.objects.create(category="Payments", question="How do deposits work?", answer="Deposits use M-Pesa.")

    def test_support_center_requires_login_and_renders(self):
        response = self.client.get(reverse("support_center"))
        self.assertEqual(response.status_code, 302)

        self.client.force_login(self.user)
        response = self.client.get(reverse("support_center"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Support center")

    def test_create_ticket_stores_initial_message(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("support_ticket_create"),
            {
                "subject": "Deposit missing",
                "category": SupportTicket.Category.PAYMENT,
                "priority": SupportTicket.Priority.NORMAL,
                "contact_email": self.user.email,
                "contact_phone": self.user.phone_number,
                "message": "I paid but my wallet is not updated.",
            },
        )

        self.assertEqual(response.status_code, 302)
        ticket = SupportTicket.objects.get(user=self.user)
        self.assertEqual(ticket.subject, "Deposit missing")
        self.assertEqual(ticket.replies.count(), 1)

    def test_ticket_reply_updates_status(self):
        ticket = SupportTicket.objects.create(user=self.user, subject="Job issue", category=SupportTicket.Category.JOBS)
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse("support_ticket_detail", kwargs={"pk": ticket.pk}),
            {"action": "reply", "message": "Please send the job reference."},
        )

        ticket.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ticket.status, SupportTicket.Status.WAITING_USER)
        self.assertEqual(SupportTicketReply.objects.filter(ticket=ticket, is_staff_reply=True).count(), 1)

    def test_staff_queue_renders_ticket(self):
        SupportTicket.objects.create(user=self.user, subject="Withdrawal issue")
        self.client.force_login(self.staff)

        response = self.client.get(reverse("support_ticket_queue"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Withdrawal issue")

    def test_policy_and_faq_pages_are_public(self):
        policy_response = self.client.get(reverse("policy_detail", kwargs={"slug": self.policy.slug}))
        faq_response = self.client.get(reverse("faq_list"))

        self.assertEqual(policy_response.status_code, 200)
        self.assertContains(policy_response, "Minimum withdrawals")
        self.assertEqual(faq_response.status_code, 200)
        self.assertContains(faq_response, "How do deposits work?")
