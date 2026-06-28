from django import forms

from .mpesa import normalize_phone_number


class MpesaPhoneForm(forms.Form):
    phone_number = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={"placeholder": "0700 000 000"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def clean_phone_number(self):
        phone_number = normalize_phone_number(self.cleaned_data["phone_number"])
        if not phone_number.startswith("254") or len(phone_number) < 12:
            raise forms.ValidationError("Enter a valid Kenyan M-Pesa phone number.")
        return phone_number


class DepositForm(MpesaPhoneForm):
    amount = forms.DecimalField(max_digits=14, decimal_places=2, min_value=1)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["amount"].widget.attrs["class"] = "form-control"
        self.fields["amount"].widget.attrs["placeholder"] = "Amount in KES"
