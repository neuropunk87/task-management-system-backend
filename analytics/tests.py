from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APIClient

from analytics.models import ProjectAnalytics
from projects.models import Project
from tasks.models import Task


User = get_user_model()


class AnalyticsSecurityTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "root", "root@example.com", "password"
        )
        self.project = Project.objects.create(
            name='unsafe </script><script>alert("x")</script>',
            owner=self.admin,
        )

    def test_completion_average_uses_completed_timestamp(self):
        with self.captureOnCommitCallbacks(execute=True):
            task = Task.objects.create(
                project=self.project,
                title="Completed analytics task",
                deadline=timezone.now() + timedelta(days=1),
                status=Task.Status.COMPLETED,
                created_by=self.admin,
            )
        completed_at = task.completed_at
        task.description = "A later unrelated edit"
        with self.captureOnCommitCallbacks(execute=True):
            task.save()
        analytics = ProjectAnalytics.objects.get(project=self.project)
        self.assertEqual(task.completed_at, completed_at)
        self.assertIsNotNone(analytics.average_completion_time)
        self.assertGreaterEqual(analytics.average_completion_time, timedelta(0))

    def test_admin_chart_escapes_script_terminators(self):
        ProjectAnalytics.objects.get_or_create(project=self.project)
        self.client.force_login(self.admin)
        response = self.client.get(
            "/secretadmin/analytics/projectanalytics/analytics-charts/"
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertNotIn('</script><script>alert("x")</script>', content)
        self.assertIn("\\u003C/script\\u003E", content)

    def test_analytics_requires_system_admin_not_project_membership(self):
        user = User.objects.create_user("ordinary", "ordinary@example.com", "password")
        self.project.participants.add(user)
        client = APIClient()
        client.force_authenticate(user)
        self.assertEqual(client.get(f"/api/analytics/{self.project.pk}/").status_code, 403)

    def test_system_admin_can_read_project_analytics(self):
        client = APIClient()
        client.force_authenticate(self.admin)
        response = client.get(f"/api/analytics/{self.project.pk}/")
        self.assertEqual(response.status_code, 200, response.data)
