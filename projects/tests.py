from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from projects.models import Project


User = get_user_model()


class ProjectAuthorizationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", "owner@example.com", "password")
        self.member = User.objects.create_user("member", "member@example.com", "password")
        self.outsider = User.objects.create_user("outsider", "outsider@example.com", "password")
        self.admin = User.objects.create_user(
            "admin",
            "admin@example.com",
            "password",
            role=User.Role.ADMIN,
        )
        self.project = Project.objects.create(name="Secure project", owner=self.owner)
        self.project.participants.add(self.member)

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_member_can_read_but_cannot_modify_project(self):
        detail_url = f"/api/projects/{self.project.pk}/"
        self.assertEqual(self.client_for(self.member).get(detail_url).status_code, 200)
        response = self.client_for(self.member).patch(
            detail_url,
            {"name": "Hijacked"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_outsider_cannot_discover_project(self):
        response = self.client_for(self.outsider).get(
            f"/api/projects/{self.project.pk}/"
        )
        self.assertEqual(response.status_code, 404)

    def test_owner_field_is_not_client_writable(self):
        response = self.client_for(self.owner).patch(
            f"/api/projects/{self.project.pk}/",
            {"owner": self.outsider.pk, "description": "updated"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.project.refresh_from_db()
        self.assertEqual(self.project.owner, self.owner)

    def test_system_admin_can_see_all_projects(self):
        response = self.client_for(self.admin).get("/api/projects/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_hidden_project_name_does_not_block_or_reveal_creation(self):
        response = self.client_for(self.outsider).post("/api/projects/", {
            "name": self.project.name, "participants": [self.outsider.pk],
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)

    def test_duplicate_project_name_for_same_owner_is_rejected(self):
        response = self.client_for(self.owner).post("/api/projects/", {
            "name": self.project.name, "participants": [self.owner.pk],
        }, format="json")
        self.assertEqual(response.status_code, 400)
