from rest_framework import serializers
from tasks.models import Task, Comment, TaskHistory
from users.models import CustomUser
from users.serializers import UserSerializer


class TaskSerializer(serializers.ModelSerializer):
    assigned_to = UserSerializer(many=True, read_only=True)
    assigned_to_ids = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.all(),
        many=True,
        write_only=True,
        source='assigned_to'
    )

    class Meta:
        model = Task
        fields = '__all__'
        read_only_fields = ['created_by', 'modified_by', 'created_at', 'modified_at']

    def create(self, validated_data):
        assigned_users = validated_data.pop('assigned_to_ids', [])
        task = Task.objects.create(**validated_data)
        task.assigned_to.set(assigned_users)
        return task

    def update(self, instance, validated_data):
        assigned_users = validated_data.pop('assigned_to_ids', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if assigned_users is not None:
            instance.assigned_to.set(assigned_users)
        instance.save()
        return instance


class TaskHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskHistory
        fields = '__all__'
        read_only_fields = '__all__'


class CommentSerializer(serializers.ModelSerializer):
    task_id = serializers.PrimaryKeyRelatedField(source='task', queryset=Task.objects.all(), write_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'task', 'task_id', 'author', 'content', 'created_at', 'modified_at']
        # fields = '__all__'
        read_only_fields = ['task', 'author', 'created_at']
