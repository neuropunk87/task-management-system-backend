from django.contrib import admin
from django.template.response import TemplateResponse
from django.urls import path

from analytics.models import ProjectAnalytics
from users.permissions import RoleRestrictedAdminMixin


@admin.register(ProjectAnalytics)
class ProjectAnalyticsAdmin(RoleRestrictedAdminMixin, admin.ModelAdmin):
    readonly_fields = [field.name for field in ProjectAnalytics._meta.fields]
    list_display = (
        "project",
        "total_tasks",
        "completed_tasks",
        "in_progress_tasks",
        "pending_tasks",
        "average_completion_time",
    )
    search_fields = ("project__name",)
    ordering = ("-total_tasks",)
    change_list_template = "admin/analytics/projectanalytics/change_list.html"
    actions = ["update_project_analytics"]

    @admin.action(description="Update selected projects' analytics")
    def update_project_analytics(self, request, queryset):
        for analytics in queryset:
            analytics.update_analytics()

    def get_urls(self):
        custom_urls = [
            path(
                "analytics-charts/",
                self.admin_site.admin_view(self.analytics_charts_view),
                name="analytics_charts",
            )
        ]
        return custom_urls + super().get_urls()

    def analytics_charts_view(self, request):
        projects = ProjectAnalytics.objects.select_related("project")
        data = {
            "labels": [item.project.name for item in projects],
            "total_tasks": [item.total_tasks for item in projects],
            "completed_tasks": [item.completed_tasks for item in projects],
            "in_progress_tasks": [item.in_progress_tasks for item in projects],
            "pending_tasks": [item.pending_tasks for item in projects],
        }
        return TemplateResponse(
            request,
            "admin/analytics_charts.html",
            {"data": data, "opts": self.model._meta},
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
