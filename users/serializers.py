from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _


User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data['role'] = self.user.role
        return data


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'first_name', 'last_name', 'telegram_id',
                  'telegram_notifications_enabled', 'phone_number', 'date_of_birth', 'avatar']


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password2']

    def validate(self, attrs):
        if attrs['password'] != attrs.pop('password2'):
            raise serializers.ValidationError({'password': _('Passwords do not match.')})
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True, required=True, validators=[validate_password])

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError(_('Old password is incorrect'))
        return value

    def update(self, instance, validated_data):
        instance.set_password(validated_data['new_password'])
        instance.save()
        return instance


class UserDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'first_name', 'last_name', 'telegram_id',
                  'telegram_notifications_enabled', 'phone_number', 'date_of_birth', 'avatar']

        read_only_fields = ['id', 'username', 'email', 'role']


class AvatarSerializer(serializers.ModelSerializer):
    avatar = serializers.ImageField(required=True, allow_null=False, use_url=True)

    class Meta:
        model = User
        fields = ['id', 'avatar']
        read_only_fields = ['id']

    def validate_avatar(self, value):
        max_size_mb = 2
        if value.size > max_size_mb * 1024 * 1024:
            raise serializers.ValidationError(f"File size must not exceed {max_size_mb} MB.")
        if not value.content_type.startswith("image/"):
            raise serializers.ValidationError("File must be an image.")
        return value

    def update(self, instance, validated_data):
        if instance.avatar and instance.avatar.storage.exists(instance.avatar.name):
            instance.avatar.delete()
        instance.avatar = validated_data.get('avatar')
        instance.save()
        return instance
