from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.core.exceptions import ValidationError


User = get_user_model()


class BootstrapFormMixin:
    def apply_bootstrap(self):
        for field in self.fields.values():
            css_class = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css_class} form-control".strip()


class LoginForm(BootstrapFormMixin, AuthenticationForm):
    username = forms.CharField(
        label="Username, phone, or email",
        widget=forms.TextInput(
            attrs={
                "autocomplete": "username",
                "placeholder": "e.g. tamara30, 0700..., or you@email.com",
            }
        ),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "current-password",
                "placeholder": "Enter your password",
            }
        )
    )

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.apply_bootstrap()


class RegistrationForm(BootstrapFormMixin, forms.ModelForm):
    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "new-password",
                "placeholder": "Create a strong password",
            }
        ),
    )
    password2 = forms.CharField(
        label="Confirm password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "new-password",
                "placeholder": "Repeat your password",
            }
        ),
    )
    referral_code = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Optional invite code"}),
    )

    class Meta:
        model = User
        fields = ("username", "email", "phone_number", "country")
        widgets = {
            "username": forms.TextInput(
                attrs={
                    "autocomplete": "username",
                    "placeholder": "Choose a username",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "autocomplete": "email",
                    "placeholder": "you@example.com",
                }
            ),
            "phone_number": forms.TextInput(
                attrs={
                    "autocomplete": "tel",
                    "placeholder": "0700 000 000",
                }
            ),
            "country": forms.TextInput(attrs={"placeholder": "Kenya"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("A user with this email already exists.")
        return email

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get("phone_number")
        if not phone_number:
            raise ValidationError("Phone number is required.")
        normalized = User.normalize_phone_number(phone_number)
        if User.objects.filter(phone_number=normalized).exists():
            raise ValidationError("A user with this phone number already exists.")
        return normalized

    def clean_referral_code(self):
        referral_code = self.cleaned_data.get("referral_code", "").strip().upper()
        if not referral_code:
            return ""
        if not User.objects.filter(referral_code__iexact=referral_code).exists():
            raise ValidationError("This referral code was not found.")
        return referral_code

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError("The two password fields did not match.")
        password_validation.validate_password(password2, self.instance)
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        referral_code = self.cleaned_data.get("referral_code")
        if referral_code:
            user.referred_by = User.objects.filter(referral_code__iexact=referral_code).first()
        if commit:
            user.save()
        return user


class ProfileForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone_number", "country")
        widgets = {
            "first_name": forms.TextInput(attrs={"placeholder": "First name"}),
            "last_name": forms.TextInput(attrs={"placeholder": "Last name"}),
            "email": forms.EmailInput(attrs={"placeholder": "you@example.com"}),
            "phone_number": forms.TextInput(attrs={"placeholder": "2547..."}),
            "country": forms.TextInput(attrs={"placeholder": "Kenya"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_bootstrap()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        exists = User.objects.exclude(pk=self.instance.pk).filter(email__iexact=email).exists()
        if exists:
            raise ValidationError("A user with this email already exists.")
        return email

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get("phone_number")
        if not phone_number:
            return None
        normalized = User.normalize_phone_number(phone_number)
        exists = User.objects.exclude(pk=self.instance.pk).filter(phone_number=normalized).exists()
        if exists:
            raise ValidationError("A user with this phone number already exists.")
        return normalized


class StyledPasswordChangeForm(BootstrapFormMixin, PasswordChangeForm):
    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs["placeholder"] = field.label
            if name == "old_password":
                field.widget.attrs["autocomplete"] = "current-password"
            else:
                field.widget.attrs["autocomplete"] = "new-password"
        self.apply_bootstrap()
