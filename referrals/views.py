from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse

from .models import ReferralBonus


User = get_user_model()
PENDING_REFERRAL_SESSION_KEY = "pending_referral_code"


def join_with_referral(request, code):
    referral_code = code.strip().upper()
    referrer = User.objects.filter(referral_code__iexact=referral_code).first()
    if not referrer:
        messages.error(request, "That referral link is not valid. Please ask for a new invite link.")
        return redirect("register")

    request.session[PENDING_REFERRAL_SESSION_KEY] = referrer.referral_code
    if request.user.is_authenticated:
        if request.user.pk == referrer.pk:
            messages.error(request, "You cannot join with your own referral link.")
            return redirect("referral_dashboard")
        if not request.user.referred_by_id and not request.user.is_staff:
            request.user.referred_by = referrer
            request.user.save(update_fields=["referred_by"])
            messages.success(request, "Referral link applied to your account.")
            return redirect("dashboard")
        messages.info(request, "Your account already has a referral.")
        return redirect("dashboard")

    register_url = f"{reverse('register')}?ref={referrer.referral_code}"
    return redirect(register_url)


@login_required
def referral_dashboard(request):
    direct_referrals = request.user.direct_referrals.order_by("-date_joined")
    bonuses = ReferralBonus.objects.filter(referrer=request.user).select_related("referred_user")[:25]
    referral_path = reverse("referral_join", kwargs={"code": request.user.referral_code})
    referral_link = request.build_absolute_uri(referral_path)
    totals = {
        "invited": direct_referrals.count(),
        "active": direct_referrals.filter(status="active").count(),
        "pending_bonus": sum(bonus.amount for bonus in bonuses if bonus.status == ReferralBonus.Status.PENDING),
        "credited_bonus": sum(bonus.amount for bonus in bonuses if bonus.status == ReferralBonus.Status.CREDITED),
    }
    return render(
        request,
        "referrals/dashboard.html",
        {
            "direct_referrals": direct_referrals[:25],
            "bonuses": bonuses,
            "totals": totals,
            "referral_link": referral_link,
        },
    )
