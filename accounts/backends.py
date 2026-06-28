from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class UsernameEmailPhoneBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        login = username or kwargs.get("email") or kwargs.get("phone_number")
        if not login or not password:
            return None

        UserModel = get_user_model()
        normalized_phone = UserModel.normalize_phone_number(login)
        try:
            user = UserModel.objects.get(
                Q(username__iexact=login)
                | Q(email__iexact=login)
                | Q(phone_number=normalized_phone)
            )
        except UserModel.DoesNotExist:
            UserModel().set_password(password)
            return None
        except UserModel.MultipleObjectsReturned:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
