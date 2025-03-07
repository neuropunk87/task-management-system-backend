from rest_framework import serializers
from projects.models import Project
from users.models import CustomUser


class ParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email']


class ProjectSerializer(serializers.ModelSerializer):
    owner = ParticipantSerializer(read_only=True)
    participants = ParticipantSerializer(many=True, read_only=True)

    class Meta:
        model = Project
        fields = ['id', 'name', 'description', 'owner', 'participants', 'status', 'created_at', 'updated_at']


class ProjectCreateUpdateSerializer(serializers.ModelSerializer):
    participants = serializers.PrimaryKeyRelatedField(
        many=True, queryset=CustomUser.objects.all(), required=True
    )

    class Meta:
        model = Project
        fields = ['name', 'description', 'owner', 'participants', 'status']

    def validate(self, attrs):
        if not attrs.get('participants'):
            raise serializers.ValidationError("At least one participant must be added to the project.")
        if not attrs.get('owner'):
            raise serializers.ValidationError("Owner cannot be empty.")
        return attrs

    # def validate_participants(self, value):
    #     if not value:
    #         raise serializers.ValidationError("At least one participant must be added to the project.")
    #     return value
