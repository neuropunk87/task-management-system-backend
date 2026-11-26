from rest_framework import serializers

from projects.models import Project
from users.models import CustomUser
from users.serializers import UserSerializer


class ProjectSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    participants = UserSerializer(many=True, read_only=True)

    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "description",
            "owner",
            "participants",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ProjectCreateUpdateSerializer(serializers.ModelSerializer):
    description = serializers.CharField(required=False, allow_blank=True, max_length=20_000)
    owner = UserSerializer(read_only=True)
    participants = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=CustomUser.objects.filter(is_active=True),
        required=False,
    )

    class Meta:
        model = Project
        fields = ["id", "name", "description", "owner", "participants", "status"]
        read_only_fields = ["id", "owner"]
        validators = []

    def validate(self, attrs):
        name = attrs.get("name", getattr(self.instance, "name", None))
        owner = self.instance.owner if self.instance else self.context["request"].user
        duplicates = Project.objects.filter(owner=owner, name=name)
        if self.instance:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError({"name": "A project with this name already exists for this owner."})
        if self.instance is None and not attrs.get("participants"):
            raise serializers.ValidationError(
                {"participants": "At least one participant must be added."}
            )
        if "participants" in attrs and not attrs["participants"]:
            raise serializers.ValidationError(
                {"participants": "At least one participant must be added."}
            )
        return attrs

    def validate_name(self, value):
        value = value.strip()
        if "\r" in value or "\n" in value:
            raise serializers.ValidationError("Project name must be a single line.")
        return value
