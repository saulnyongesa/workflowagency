from django import forms
from django.contrib.auth import get_user_model

from .models import SupportTicket, SupportTicketReply


User = get_user_model()


class SupportTicketForm(forms.ModelForm):
    message = forms.CharField(widget=forms.Textarea(attrs={"rows": 5}), max_length=3000)

    class Meta:
        model = SupportTicket
        fields = ("subject", "category", "priority", "contact_email", "contact_phone")

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields["contact_email"].initial = user.email
            self.fields["contact_phone"].initial = user.phone_number
        for field in self.fields.values():
            css_class = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            field.widget.attrs["class"] = css_class


class SupportTicketReplyForm(forms.ModelForm):
    class Meta:
        model = SupportTicketReply
        fields = ("message",)
        widgets = {"message": forms.Textarea(attrs={"rows": 4, "class": "form-control"})}


class StaffTicketUpdateForm(forms.ModelForm):
    class Meta:
        model = SupportTicket
        fields = ("status", "assigned_to", "admin_notes")
        widgets = {
            "status": forms.Select(attrs={"class": "form-select"}),
            "assigned_to": forms.Select(attrs={"class": "form-select"}),
            "admin_notes": forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = User.objects.filter(is_staff=True).order_by("username")
        self.fields["assigned_to"].required = False
