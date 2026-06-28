from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class AccountFlowTests(TestCase):
    def test_user_can_register_and_starts_locked(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "tamara30",
                "email": "tamara@example.com",
                "phone_number": "0700000000",
                "country": "Kenya",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertRedirects(response, reverse("dashboard"))
        user = User.objects.get(username="tamara30")
        self.assertEqual(user.phone_number, "254700000000")
        self.assertEqual(user.status, User.AccountStatus.LOCKED)
        self.assertEqual(user.activation_status, User.ActivationStatus.NOT_ACTIVATED)
        self.assertTrue(user.referral_code)

    def test_user_can_login_with_email(self):
        User.objects.create_user(
            username="emailuser",
            email="emailuser@example.com",
            phone_number="254711111111",
            password="StrongPass123!",
        )

        response = self.client.post(
            reverse("login"),
            {"username": "emailuser@example.com", "password": "StrongPass123!"},
        )

        self.assertRedirects(response, reverse("dashboard"))

    def test_user_can_login_with_phone(self):
        User.objects.create_user(
            username="phoneuser",
            email="phoneuser@example.com",
            phone_number="254722222222",
            password="StrongPass123!",
        )

        response = self.client.post(
            reverse("login"),
            {"username": "0722222222", "password": "StrongPass123!"},
        )

        self.assertRedirects(response, reverse("dashboard"))

    def test_profile_update_normalizes_phone(self):
        user = User.objects.create_user(
            username="profileuser",
            email="profileuser@example.com",
            phone_number="254733333333",
            password="StrongPass123!",
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
