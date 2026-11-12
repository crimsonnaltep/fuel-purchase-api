from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.utils import get_md5_hash_password
from rest_framework_simplejwt.views import TokenRefreshView


class RefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        token = self.token_class(attrs["refresh"])
        account = (
            get_user_model()
            .objects.filter(pk=token[api_settings.USER_ID_CLAIM], is_active=True)
            .first()
        )
        if account is None:
            raise AuthenticationFailed("Account is unavailable.")
        if token.get(api_settings.REVOKE_TOKEN_CLAIM) != get_md5_hash_password(
            account.password
        ):
            raise AuthenticationFailed("Password changed. Sign in again.")
        return super().validate(attrs)


class RefreshView(TokenRefreshView):
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
