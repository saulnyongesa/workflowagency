from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import ProfileForm, ReferralCompletionForm, RegistrationForm, StyledPasswordChangeForm


User = get_user_model()
PENDING_REFERRAL_SESSION_KEY = "pending_referral_code"


def _pending_referral_code(request):
    code = (request.GET.get("ref") or request.session.get(PENDING_REFERRAL_SESSION_KEY) or "").strip().upper()
    if not code:
        return ""
    referrer = User.objects.filter(referral_code__iexact=code).first()
    if not referrer:
        request.session.pop(PENDING_REFERRAL_SESSION_KEY, None)
        if request.GET.get("ref"):
            messages.error(request, "That referral link is not valid. Please ask for a new invite link.")
        return ""
    request.session[PENDING_REFERRAL_SESSION_KEY] = referrer.referral_code
    return referrer.referral_code


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    referral_code = _pending_referral_code(request)
    form = RegistrationForm(
        request.POST or None,
        locked_referral_code=referral_code,
        initial={"referral_code": referral_code} if referral_code else None,
    )
    if request.method == "POST" and form.is_valid():
        user = form.save()
        request.session.pop(PENDING_REFERRAL_SESSION_KEY, None)
        login(request, user, backend="accounts.backends.UsernameEmailPhoneBackend")
        messages.success(
            request,
            "Account created. Complete activation to unlock jobs and withdrawals.",
        )
        return redirect("dashboard")

    return render(request, "accounts/register.html", {"form": form, "referral_code_applied": referral_code})


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
        return redirect("profile")

    return render(request, "accounts/profile.html", {"form": form})


@login_required
def password_change(request):
    form = StyledPasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, "Password updated.")
        return redirect("profile")

    return render(request, "accounts/password_change.html", {"form": form})


@login_required
def complete_referral(request):
    if request.user.referred_by_id or request.user.is_staff:
        return redirect("dashboard")

    form = ReferralCompletionForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Referral code saved. You can now continue.")
        return redirect("dashboard")

    return render(request, "accounts/complete_referral.html", {"form": form})
