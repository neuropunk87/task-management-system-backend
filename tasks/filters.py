from django_filters import rest_framework as filters
from tasks.models import Task


class TaskFilter(filters.FilterSet):
    priority = filters.ChoiceFilter(choices=Task.Priority.choices)
    status = filters.ChoiceFilter(choices=Task.Status.choices)
    deadline = filters.DateFromToRangeFilter()
    project = filters.CharFilter(field_name="project__name", lookup_expr='icontains')
    assigned_to = filters.CharFilter(field_name="assigned_to__username", lookup_expr='icontains')

    class Meta:
        model = Task
        fields = ['priority', 'status', 'deadline', 'project', 'assigned_to']
