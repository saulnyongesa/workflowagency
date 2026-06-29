from django.shortcuts import redirect
from django.urls import reverse


class ReferralRequiredMiddleware:
    """Require existing non-staff users without a referrer to add a referral code."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user and user.is_authenticated and not user.is_staff and not user.referred_by_id:
            allowed_prefixes = (
                reverse("complete_referral"),
                reverse("logout"),
                "/referrals/join/",
                "/static/",
                "/media/",
            )
            if not request.path.startswith(allowed_prefixes):
                return redirect("complete_referral")
        return self.get_response(request)
