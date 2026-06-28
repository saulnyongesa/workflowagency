from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import ReferralBonus


@login_required
def referral_dashboard(request):
    direct_referrals = request.user.direct_referrals.order_by("-date_joined")
    bonuses = ReferralBonus.objects.filter(referrer=request.user).select_related("referred_user")[:25]
    totals = {
        "invited": direct_referrals.count(),
        "active": direct_referrals.filter(status="active").count(),
        "pending_bonus": sum(bonus.amount for bonus in bonuses if bonus.status == ReferralBonus.Status.PENDING),
        "credited_bonus": sum(bonus.amount for bonus in bonuses if bonus.status == ReferralBonus.Status.CREDITED),
    }
    return render(
        request,
        "referrals/dashboard.html",
        {"direct_referrals": direct_referrals[:25], "bonuses": bonuses, "totals": totals},
    )
