from django import forms
from django.contrib.auth import get_user_model

from .models import LedgerTransaction


User = get_user_model()


class AdminWalletAdjustmentForm(forms.Form):
    user = forms.ModelChoiceField(queryset=User.objects.order_by("username"))
    direction = forms.ChoiceField(choices=LedgerTransaction.Direction.choices)
    balance_bucket = forms.ChoiceField(choices=LedgerTransaction.BalanceBucket.choices)
    amount = forms.DecimalField(max_digits=14, decimal_places=2, min_value=0.01)
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), max_length=255)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css_class = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css_class} form-control".strip()


class WithdrawalRequestForm(forms.Form):
    amount = forms.DecimalField(max_digits=14, decimal_places=2, min_value=0.01)
    phone_number = forms.CharField(max_length=20)

    def __init__(self, *args, initial_phone="", **kwargs):
        super().__init__(*args, **kwargs)
        if initial_phone:
            self.fields["phone_number"].initial = initial_phone
        self.fields["amount"].widget.attrs.update({"class": "form-control", "placeholder": "Amount in KES"})
        self.fields["phone_number"].widget.attrs.update({"class": "form-control", "placeholder": "2547..."})


class WithdrawalRejectForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), max_length=255)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["reason"].widget.attrs["class"] = "form-control"


class WithdrawalPaidForm(forms.Form):
    payout_reference = forms.CharField(max_length=80, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["payout_reference"].widget.attrs.update(
            {"class": "form-control", "placeholder": "M-Pesa/manual payout reference"}
        )
