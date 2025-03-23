from django.contrib import admin
from django.urls import path
from django.template.response import TemplateResponse
import json
from analytics.models import ProjectAnalytics


@admin.register(ProjectAnalytics)
class ProjectAnalyticsAdmin(admin.ModelAdmin):
    readonly_fields = [field.name for field in ProjectAnalytics._meta.fields]
    list_display = ('project', 'total_tasks', 'completed_tasks', 'in_progress_tasks', 'pending_tasks', 'average_completion_time')
    search_fields = ('project__name',)
    ordering = ('-total_tasks',)
    change_list_template = "admin/analytics/projectanalytics/change_list.html"

    fieldsets = (
        ('Project Analytics', {
            'fields': ('project', 'total_tasks', 'completed_tasks', 'in_progress_tasks', 'pending_tasks', 'average_completion_time'),
        }),
    )

    actions = ['update_project_analytics']

    @admin.action(description="Update selected projects' analytics")
    def update_project_analytics(self, request, queryset):
        for analytics in queryset:
            analytics.update_analytics()

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('analytics-charts/', self.admin_site.admin_view(self.analytics_charts_view), name="analytics_charts"),
        ]
        return custom_urls + urls

    def analytics_charts_view(self, request):
        projects = ProjectAnalytics.objects.all()
        data = {
            "labels": [analytics.project.name for analytics in projects],
            "total_tasks": [analytics.total_tasks for analytics in projects],
            "completed_tasks": [analytics.completed_tasks for analytics in projects],
            "in_progress_tasks": [analytics.in_progress_tasks for analytics in projects],
            "pending_tasks": [analytics.pending_tasks for analytics in projects],
        }

        context = {
            "data": json.dumps(data),
            "opts": self.model._meta,
        }
        return TemplateResponse(request, "admin/analytics_charts.html", context)

    def has_add_permission(self, request):
        return False  # Видалення кнопки "Add project analytics"

    def has_change_permission(self, request, obj=None):
        return False  # Видалення кнопок "Save", "Save and continue editing", "Save and add another"

    def has_delete_permission(self, request, obj=None):
        return False  # Видалення кнопки "Delete"
