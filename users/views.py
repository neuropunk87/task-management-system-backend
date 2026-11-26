from urllib.parse import quote

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import status
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView, RetrieveAPIView, RetrieveUpdateAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.utils import extend_schema

from notifications.delivery import queue_welcome_email
from users.serializers import (
    AvatarSerializer,
    ChangePasswordSerializer,
    CustomTokenObtainPairSerializer,
    CustomTokenRefreshSerializer,
    LogoutSerializer,
    TelegramLinkResponseSerializer,
    UserDetailSerializer,
    UserRegistrationSerializer,
    UserSerializer,
)
from users.telegram import issue_telegram_link, unlink_telegram


User = get_user_model()


@method_decorator(never_cache, name="dispatch")
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


@method_decorator(never_cache, name="dispatch")
class CustomTokenRefreshView(TokenRefreshView):
    serializer_class = CustomTokenRefreshSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "refresh"


class UserRegistrationView(APIView):
    permission_classes = [AllowAny]
    serializer_class = UserRegistrationSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "registration"

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                user = serializer.save()
                queue_welcome_email(user)
        except IntegrityError as exc:
            # Concurrent registrations must not turn a unique constraint into a 500.
            raise ValidationError("Username or email is already registered.") from exc
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "credential_change"

    def post(self, request):
        with transaction.atomic():
            request.user = User.objects.select_for_update().get(pk=request.user.pk)
            serializer = self.serializer_class(
                data=request.data, context={"request": request},
            )
            serializer.is_valid(raise_exception=True)
            serializer.update(request.user, serializer.validated_data)

            # A password change is a security boundary: revoke every refresh token.
            for token in OutstandingToken.objects.filter(user=request.user):
                BlacklistedToken.objects.get_or_create(token=token)
        return Response({"message": "Password updated successfully."})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LogoutSerializer

    def post(self, request):
        serializer = self.serializer_class(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "Logout successful."})


class UserProfileView(RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    serializer_class = UserDetailSerializer

    def get_object(self):
        return self.request.user


class UpdateAvatarView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AvatarSerializer
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "avatar_upload"

    def put(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            instance=request.user,
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"message": "Avatar updated successfully.", "data": serializer.data}
        )


@method_decorator(never_cache, name="dispatch")
class TelegramLinkView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "telegram_link"

    @extend_schema(request=None, responses=TelegramLinkResponseSerializer)
    def post(self, request):
        if not settings.TELEGRAM_BOT_TOKEN:
            return Response({"detail": "Telegram integration is not configured."}, status=503)
        token, expires_at = issue_telegram_link(request.user)
        bot_username = settings.TELEGRAM_BOT_USERNAME
        link = (
            f"https://t.me/{quote(bot_username)}?start={quote(token)}"
            if bot_username
            else None
        )
        return Response(
            {
                "link": link,
                "start_parameter": token,
                "expires_at": expires_at,
            }
        )

    @extend_schema(request=None, responses={204: None})
    def delete(self, request):
        unlink_telegram(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["username", "first_name", "last_name", "role"]
    ordering_fields = ["username", "first_name", "last_name", "role"]
    ordering = ["id"]

    def get_queryset(self):
        return User.objects.filter(is_active=True)


class UserDetailView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer
    lookup_field = "pk"

    def get_queryset(self):
        return User.objects.filter(is_active=True)
