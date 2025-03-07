from django.contrib import admin
from projects.models import Project
from users.permissions import RoleRestrictedModelAdmin


@admin.register(Project)
class ProjectAdmin(RoleRestrictedModelAdmin):
# class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'get_participants', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'owner', 'created_at', 'updated_at')
    filter_horizontal = ('participants',)  # Працює тільки в формі редагування
    search_fields = ('name', 'owner__username', 'description')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('General Information', {'fields': ('name', 'description', 'owner', 'participants', 'status')}),
        ('Dates', {'fields': ('created_at', 'updated_at')}),
    )

    actions = ['archive_projects', 'unarchive_projects']

    @admin.display(description="Participants")  # Назва колонки в адмінці
    def get_participants(self, obj):
        return ", ".join([user.username for user in obj.participants.all()])

    @admin.action(description="Archive selected projects")
    def archive_projects(self, request, queryset):
        queryset.update(status=Project.Status.ARCHIVED)
        # queryset.update(status='archived')

    @admin.action(description="Unarchive selected projects")
    def unarchive_projects(self, request, queryset):
        queryset.update(status=Project.Status.ACTIVE)
        # queryset.update(status='active')
