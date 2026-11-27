from io import BytesIO
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from PIL import Image
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from rest_framework_simplejwt.utils import get_md5_hash_password


User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # SimpleJWT builds these fields in its own __init__, overwriting any
        # class declaration. Bound input and preserve the registered password.
        self.fields[self.username_field] = serializers.CharField(write_only=True, max_length=150)
        self.fields["password"] = serializers.CharField(
            write_only=True, trim_whitespace=False, max_length=128,
            style={"input_type": "password"},
        )

    def validate(self, attrs):
        data = super().validate(attrs)
        data["role"] = self.user.role
        return data

class CustomTokenRefreshSerializer(TokenRefreshSerializer):
    refresh = serializers.CharField(max_length=4096, trim_whitespace=True)

    @transaction.atomic
    def validate(self, attrs):
        token = RefreshToken(attrs["refresh"])
        user = User.objects.select_for_update().filter(
            pk=token.get(api_settings.USER_ID_CLAIM), is_active=True
        ).first()
        if not user or token.get(api_settings.REVOKE_TOKEN_CLAIM) != get_md5_hash_password(user.password):
            raise AuthenticationFailed("Invalid or revoked refresh token.")
        # Serialization on the user's row also prevents two rotations of one token.
        return super().validate(attrs)


class UserSerializer(serializers.ModelSerializer):
    """Public user directory representation without private contact data."""

    class Meta:
        model = User
        fields = ["id", "username", "role", "first_name", "last_name", "avatar"]
        read_only_fields = fields


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        trim_whitespace=False,
        max_length=128,
    )
    password2 = serializers.CharField(
        write_only=True, required=True, trim_whitespace=False, max_length=128
    )
    email = serializers.EmailField(max_length=254)

    class Meta:
        model = User
        fields = ["username", "email", "password", "password2"]

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(_("An account with this email already exists."))
        return value

    def validate(self, attrs):
        password2 = attrs.pop("password2")
        if attrs["password"] != password2:
            raise serializers.ValidationError({"password": _("Passwords do not match.")})
        try:
            validate_password(attrs["password"], User(**attrs))
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": exc.messages}) from exc
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(
        write_only=True, required=True, trim_whitespace=False, max_length=128
    )
    new_password = serializers.CharField(
        write_only=True,
        required=True,
        trim_whitespace=False,
        max_length=128,
    )

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError(_("Old password is incorrect."))
        return value

    def update(self, instance, validated_data):
        instance.set_password(validated_data["new_password"])
        instance.save(update_fields=["password"])
        return instance

    def validate_new_password(self, value):
        try:
            validate_password(value, self.context["request"].user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        return value


class UserDetailSerializer(serializers.ModelSerializer):
    """Private representation used only for the authenticated user's profile."""

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "role",
            "first_name",
            "last_name",
            "telegram_id",
            "telegram_verified_at",
            "telegram_notifications_enabled",
            "phone_number",
            "date_of_birth",
            "avatar",
        ]
        read_only_fields = [
            "id",
            "username",
            "email",
            "role",
            "telegram_id",
            "telegram_verified_at",
            "avatar",
        ]

    def validate_telegram_notifications_enabled(self, value):
        if value and not (self.instance.telegram_id and self.instance.telegram_verified_at):
            raise serializers.ValidationError(
                _("Link a Telegram account before enabling notifications.")
            )
        return value


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(write_only=True, trim_whitespace=True, max_length=4096)

    def validate_refresh(self, value):
        try:
            token = RefreshToken(value)
        except TokenError as exc:
            raise serializers.ValidationError(_("Invalid or expired refresh token.")) from exc

        request = self.context["request"]
        if str(token.get(api_settings.USER_ID_CLAIM)) != str(request.user.pk):
            raise serializers.ValidationError(
                _("The refresh token does not belong to this user.")
            )
        return token

    def save(self, **kwargs):
        self.validated_data["refresh"].blacklist()


class TelegramLinkStatusSerializer(serializers.Serializer):
    verified = serializers.BooleanField()


class TelegramLinkResponseSerializer(serializers.Serializer):
    link = serializers.URLField(allow_null=True)
    start_parameter = serializers.CharField()
    expires_at = serializers.DateTimeField()


class AvatarSerializer(serializers.ModelSerializer):
    avatar = serializers.ImageField(required=True, allow_null=False, use_url=True)

    class Meta:
        model = User
        fields = ["id", "avatar"]
        read_only_fields = ["id"]

    def validate_avatar(self, value):
        max_size_mb = 2
        if value.size > max_size_mb * 1024 * 1024:
            raise serializers.ValidationError(
                f"File size must not exceed {max_size_mb} MB."
            )
        if value.content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise serializers.ValidationError("File must be a JPEG, PNG, or WebP image.")

        try:
            image = Image.open(value)
            image.verify()
            value.seek(0)
            image = Image.open(value)
            width, height = image.size
            if width > 4_096 or height > 4_096 or width * height > 4_000_000:
                raise serializers.ValidationError("Image dimensions are too large.")

            image_format = image.format
            if image_format not in {"JPEG", "PNG", "WEBP"}:
                raise serializers.ValidationError("Unsupported image format.")

            clean_image = image.copy()
            clean_image.info.clear()
            if image_format == "JPEG" and clean_image.mode not in {"RGB", "L"}:
                clean_image = clean_image.convert("RGB")
            output = BytesIO()
            clean_image.save(output, format=image_format, optimize=True)
        except serializers.ValidationError:
            raise
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            raise serializers.ValidationError(
                "The uploaded file is corrupted or is not a valid image."
            ) from exc

        extension = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}[
            image_format
        ]
        clean_bytes = output.getvalue()
        if len(clean_bytes) > max_size_mb * 1024 * 1024:
            raise serializers.ValidationError("The decoded image is too large.")
        return ContentFile(clean_bytes, name=f"{uuid4().hex}{extension}")

    def update(self, instance, validated_data):
        old_avatar = instance.avatar.name if instance.avatar else None
        storage = instance.avatar.storage if instance.avatar else None
        instance.avatar = validated_data["avatar"]
        instance.save(update_fields=["avatar"])
        if old_avatar and storage and old_avatar != instance.avatar.name:
            storage.delete(old_avatar)
        return instance
