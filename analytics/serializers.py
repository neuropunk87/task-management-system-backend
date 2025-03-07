from rest_framework import serializers
from analytics.models import ProjectAnalytics


class ProjectAnalyticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectAnalytics
        fields = ['project', 'total_tasks', 'completed_tasks', 'in_progress_tasks', 'pending_tasks', 'average_completion_time']
        read_only_fields = ['project', 'total_tasks', 'completed_tasks', 'in_progress_tasks', 'pending_tasks', 'average_completion_time']
