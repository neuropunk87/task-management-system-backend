from django.utils import timezone
from rest_framework import serializers

from tasks.models import Comment, Task, TaskHistory
from projects.models import Project
from users.access import is_system_admin
from users.models import CustomUser
from users.serializers import UserSerializer


def _can_access_project(user, project):
    return is_system_admin(user) or project.owner_id == user.pk or project.participants.filter(
        pk=user.pk
    ).exists()


class TaskSerializer(serializers.ModelSerializer):
    description = serializers.CharField(required=False, allow_blank=True, max_length=20_000)
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.none())
    assigned_to = UserSerializer(many=True, read_only=True)
    assigned_to_ids = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.filter(is_active=True),
        many=True,
        write_only=True,
        source="assigned_to",
        required=False,
    )

    class Meta:
        model = Task
        fields = [
            "id",
            "project",
            "title",
            "description",
            "priority",
            "status",
            "deadline",
            "assigned_to",
            "assigned_to_ids",
            "created_by",
            "modified_by",
            "created_at",
            "modified_at",
            "completed_at",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "modified_by",
            "created_at",
            "modified_at",
            "completed_at",
        ]

    def validate_deadline(self, value):
        if value <= timezone.now() and (
            self.instance is None or value != self.instance.deadline
        ):
            raise serializers.ValidationError("Deadline must be in the future.")
        return value

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            queryset = Project.objects.all()
            if not is_system_admin(request.user):
                from django.db.models import Q

                queryset = queryset.filter(Q(owner=request.user) | Q(participants=request.user)).distinct()
            self.fields["project"].queryset = queryset

    def validate_title(self, value):
        value = value.strip()
        if "\r" in value or "\n" in value:
            raise serializers.ValidationError("Task title must be a single line.")
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return attrs

        user = request.user
        project = attrs.get("project") or getattr(self.instance, "project", None)
        if project and not _can_access_project(user, project):
            raise serializers.ValidationError(
                {"project": "You do not have access to this project."}
            )
        if (
            self.instance is None
            and project
            and project.status != project.Status.ACTIVE
            and not is_system_admin(user)
        ):
            raise serializers.ValidationError(
                {"project": "Tasks cannot be added to an archived project."}
            )

        if (
            self.instance
            and "project" in attrs
            and project.pk != self.instance.project_id
            and not is_system_admin(user)
            and project.owner_id != user.pk
        ):
            raise serializers.ValidationError(
                {"project": "A task can be moved only to a project you own."}
            )

        assigned_users = attrs.get("assigned_to")
        if self.instance and "project" in attrs and assigned_users is None:
            assigned_users = self.instance.assigned_to.all()
        if project and assigned_users is not None:
            allowed_ids = set(project.participants.values_list("pk", flat=True))
            if project.owner_id:
                allowed_ids.add(project.owner_id)
            invalid = [user.pk for user in assigned_users if user.pk not in allowed_ids]
            if invalid:
                raise serializers.ValidationError(
                    {"assigned_to_ids": "Every assignee must belong to the project."}
                )

        if self.instance and not (
            is_system_admin(user) or self.instance.project.owner_id == user.pk
        ):
            supplied = set(self.initial_data.keys())
            if supplied - {"status"}:
                raise serializers.ValidationError(
                    "Assignees may update only the task status."
                )
        return attrs


class TaskHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskHistory
        fields = [
            "id",
            "task",
            "modified_by",
            "modified_at",
            "field_changed",
            "old_value",
            "new_value",
        ]
        read_only_fields = fields


class CommentSerializer(serializers.ModelSerializer):
    task_id = serializers.PrimaryKeyRelatedField(
        source="task",
        queryset=Task.objects.none(),
        write_only=True,
        required=False,
    )

    class Meta:
        model = Comment
        fields = [
            "id",
            "task",
            "task_id",
            "author",
            "parent",
            "content",
            "created_at",
            "modified_at",
        ]
        read_only_fields = [
            "id",
            "task",
            "author",
            "parent",
            "created_at",
            "modified_at",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            user = request.user
            queryset = Task.objects.select_related("project")
            if not is_system_admin(user):
                from django.db.models import Q

                queryset = queryset.filter(
                    Q(project__owner=user)
                    | Q(project__participants=user)
                    | Q(assigned_to=user)
                ).distinct()
            self.fields["task_id"].queryset = queryset

    def validate_content(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Comment cannot be empty.")
        if len(value) > 10_000:
            raise serializers.ValidationError("Comment is too long.")
        return value

    def validate(self, attrs):
        if self.instance is not None and "task" in attrs:
            raise serializers.ValidationError({"task_id": "A comment cannot be moved."})
        return attrs
