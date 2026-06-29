from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class AccountFlowTests(TestCase):
    def create_referrer(self, suffix="base"):
        return User.objects.create_user(
            username=f"referrer{suffix}",
            email=f"referrer{suffix}@example.com",
            phone_number=f"25471111{suffix[-4:] if suffix[-4:].isdigit() else '1111'}",
            password="StrongPass123!",
        )

    def test_user_can_register_and_starts_locked(self):
        referrer = User.objects.create_user(
            username="referrer",
            email="referrer@example.com",
            phone_number="254711111110",
            password="StrongPass123!",
        )
        response = self.client.post(
            reverse("register"),
            {
                "username": "tamara30",
                "email": "tamara@example.com",
                "phone_number": "0700000000",
                "country": "Kenya",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
                "referral_code": referrer.referral_code,
            },
        )

        self.assertRedirects(response, reverse("dashboard"))
        user = User.objects.get(username="tamara30")
        self.assertEqual(user.phone_number, "254700000000")
        self.assertEqual(user.status, User.AccountStatus.LOCKED)
        self.assertEqual(user.activation_status, User.ActivationStatus.NOT_ACTIVATED)
        self.assertTrue(user.referral_code)
        self.assertEqual(user.referred_by, referrer)

    def test_registration_requires_referral_code(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "noreferral",
                "email": "noreferral@example.com",
                "phone_number": "0700000001",
                "country": "Kenya",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="noreferral").exists())
        self.assertContains(response, "Referral code is required")

    def test_referral_link_applies_code_to_registration(self):
        referrer = self.create_referrer("0006")

        response = self.client.get(reverse("referral_join", kwargs={"code": referrer.referral_code}))

        self.assertRedirects(response, f"{reverse('register')}?ref={referrer.referral_code}")

        response = self.client.get(response.url)
        self.assertContains(response, "Referral link applied")
        self.assertContains(response, referrer.referral_code)

        response = self.client.post(
            reverse("register"),
            {
                "username": "linkreferred",
                "email": "linkreferred@example.com",
                "phone_number": "0700000006",
                "country": "Kenya",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertRedirects(response, reverse("dashboard"))
        user = User.objects.get(username="linkreferred")
        self.assertEqual(user.referred_by, referrer)

    def test_user_can_login_with_email(self):
        referrer = self.create_referrer("0002")
        User.objects.create_user(
            username="emailuser",
            email="emailuser@example.com",
            phone_number="254711111111",
            password="StrongPass123!",
            referred_by=referrer,
        )

        response = self.client.post(
            reverse("login"),
            {"username": "emailuser@example.com", "password": "StrongPass123!"},
        )

        self.assertRedirects(response, reverse("dashboard"))

    def test_user_can_login_with_phone(self):
        referrer = self.create_referrer("0003")
        User.objects.create_user(
            username="phoneuser",
            email="phoneuser@example.com",
            phone_number="254722222222",
            password="StrongPass123!",
            referred_by=referrer,
        )

        response = self.client.post(
            reverse("login"),
            {"username": "0722222222", "password": "StrongPass123!"},
        )

        self.assertRedirects(response, reverse("dashboard"))

    def test_profile_update_normalizes_phone(self):
        referrer = self.create_referrer("0004")
        user = User.objects.create_user(
            username="profileuser",
            email="profileuser@example.com",
            phone_number="254733333333",
            password="StrongPass123!",
            referred_by=referrer,
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("profile"),
            {
                "first_name": "Tamara",
                "last_name": "Main",
                "email": "profileuser@example.com",
                "phone_number": "0733333333",
                "country": "Kenya",
            },
        )

        self.assertRedirects(response, reverse("profile"))
        user.refresh_from_db()
        self.assertEqual(user.first_name, "Tamara")
        self.assertEqual(user.phone_number, "254733333333")

    def test_existing_unreferred_user_must_complete_referral(self):
        user = User.objects.create_user(
            username="legacyuser",
            email="legacyuser@example.com",
            phone_number="254744444444",
            password="StrongPass123!",
        )
        referrer = self.create_referrer("0005")
        self.client.force_login(user)

        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, reverse("complete_referral"))

        response = self.client.post(reverse("complete_referral"), {"referral_code": referrer.referral_code})

        self.assertRedirects(response, reverse("dashboard"))
        user.refresh_from_db()
        self.assertEqual(user.referred_by, referrer)
