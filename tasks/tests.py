from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from projects.models import Project
from tasks.models import Comment, Task


User = get_user_model()


class TaskAuthorizationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user("owner-t", "owner-t@example.com", "password")
        self.member = User.objects.create_user("member-t", "member-t@example.com", "password")
        self.assignee = User.objects.create_user("assigned", "assigned@example.com", "password")
        self.outsider = User.objects.create_user("outside-t", "outside-t@example.com", "password")
        self.project = Project.objects.create(name="Task project", owner=self.owner)
        self.project.participants.add(self.member, self.assignee)
        self.other_project = Project.objects.create(name="Hidden project", owner=self.outsider)
        self.task = Task.objects.create(
            project=self.project,
            title="Visible task",
            deadline=timezone.now() + timedelta(days=2),
            created_by=self.owner,
        )
        self.task.assigned_to.add(self.assignee)
        self.hidden_task = Task.objects.create(
            project=self.other_project,
            title="Hidden task",
            deadline=timezone.now() + timedelta(days=2),
            created_by=self.outsider,
        )

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_task_list_is_scoped(self):
        response = self.client_for(self.member).get("/api/tasks/tasks/")
        self.assertEqual(response.status_code, 200)
        titles = {item["title"] for item in response.data["results"]}
        self.assertEqual(titles, {"Visible task"})

    def test_assignee_can_change_only_status(self):
        url = f"/api/tasks/tasks/{self.task.pk}/"
        response = self.client_for(self.assignee).patch(
            url,
            {"status": Task.Status.IN_PROGRESS},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        denied = self.client_for(self.assignee).patch(
            url,
            {"title": "Privilege escalation"},
            format="json",
        )
        self.assertEqual(denied.status_code, 400)

    def test_unassigned_member_cannot_modify_task(self):
        response = self.client_for(self.member).patch(
            f"/api/tasks/tasks/{self.task.pk}/",
            {"status": Task.Status.COMPLETED},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    @patch("notifications.delivery.publish_delivery")
    def test_create_sets_audit_fields_and_assignees(self, mocked_email):
        response = self.client_for(self.member).post(
            "/api/tasks/tasks/",
            {
                "project": self.project.pk,
                "title": "Created safely",
                "deadline": (timezone.now() + timedelta(days=3)).isoformat(),
                "assigned_to_ids": [self.member.pk],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        task = Task.objects.get(title="Created safely")
        self.assertEqual(task.created_by, self.member)
        self.assertEqual(list(task.assigned_to.all()), [self.member])

    def test_cannot_assign_project_outsider(self):
        response = self.client_for(self.owner).post(
            "/api/tasks/tasks/",
            {
                "project": self.project.pk,
                "title": "Unsafe assignment",
                "deadline": (timezone.now() + timedelta(days=3)).isoformat(),
                "assigned_to_ids": [self.outsider.pk],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_comment_scope_and_reply(self):
        comment = Comment.objects.create(
            task=self.task,
            author=self.assignee,
            content="Original",
        )
        Comment.objects.create(
            task=self.hidden_task,
            author=self.outsider,
            content="Secret",
        )
        response = self.client_for(self.member).get("/api/tasks/comments/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

        reply = self.client_for(self.member).post(
            f"/api/tasks/comments/{comment.pk}/reply/",
            {"content": "Reply"},
            format="json",
        )
        self.assertEqual(reply.status_code, 201, reply.data)
        self.assertEqual(Comment.objects.get(pk=reply.data["id"]).parent, comment)

    def test_outsider_cannot_comment_on_hidden_task(self):
        response = self.client_for(self.member).post(
            "/api/tasks/comments/",
            {"task_id": self.hidden_task.pk, "content": "Intrusion"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_completed_at_tracks_status_transition(self):
        self.task.status = Task.Status.COMPLETED
        self.task.save()
        self.assertIsNotNone(self.task.completed_at)
        self.task.status = Task.Status.IN_PROGRESS
        self.task.save()
        self.assertIsNone(self.task.completed_at)

    def test_assignee_cannot_delete_task(self):
        url = f"/api/tasks/tasks/{self.task.pk}/"
        self.assertEqual(self.client_for(self.assignee).delete(url).status_code, 403)
        self.assertTrue(Task.objects.filter(pk=self.task.pk).exists())
        self.assertEqual(self.client_for(self.owner).delete(url).status_code, 204)

    def test_removing_project_member_revokes_assignment_and_task_access(self):
        self.project.participants.remove(self.assignee)
        self.assertFalse(self.task.assigned_to.filter(pk=self.assignee.pk).exists())
        self.assertEqual(self.client_for(self.assignee).get(f"/api/tasks/tasks/{self.task.pk}/").status_code, 404)

    def test_reverse_membership_removal_also_revokes_assignment(self):
        self.assignee.projects.remove(self.project)
        self.assertFalse(self.task.assigned_to.filter(pk=self.assignee.pk).exists())

    def test_task_cannot_be_moved_to_an_outsiders_project(self):
        response = self.client_for(self.owner).patch(f"/api/tasks/tasks/{self.task.pk}/", {
            "project": self.other_project.pk,
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.task.refresh_from_db()
        self.assertEqual(self.task.project, self.project)

    def test_invalid_comment_filter_is_400_not_500(self):
        response = self.client_for(self.member).get("/api/tasks/comments/?task_id=invalid")
        self.assertEqual(response.status_code, 400)

    def test_others_cannot_modify_comments(self):
        comment = Comment.objects.create(task=self.task, author=self.assignee, content="Mine")
        response = self.client_for(self.member).patch(f"/api/tasks/comments/{comment.pk}/", {"content": "Hijacked"}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_anonymous_cannot_access_project_task_comment_or_notification_lists(self):
        client = APIClient()
        for url in ("/api/tasks/tasks/", "/api/tasks/comments/", "/api/projects/", "/api/notifications/", "/api/users/list/", "/api/schema/"):
            self.assertEqual(client.get(url).status_code, 401, url)

    def test_hidden_task_title_does_not_block_creation_in_own_project(self):
        response = self.client_for(self.owner).post("/api/tasks/tasks/", {
            "project": self.project.pk, "title": self.hidden_task.title,
            "deadline": (timezone.now() + timedelta(days=2)).isoformat(),
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)

    def test_partial_status_save_updates_completion_and_modification_timestamps(self):
        old_modified = self.task.modified_at
        self.task.status = Task.Status.COMPLETED
        self.task.save(update_fields=["status"])
        self.task.refresh_from_db()
        self.assertIsNotNone(self.task.completed_at)
        self.assertGreater(self.task.modified_at, old_modified)
