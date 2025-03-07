from django.utils.timezone import now
from datetime import timedelta
import random
from users.models import CustomUser
from projects.models import Project
from tasks.models import Task


roles = ["admin", "manager", "employee"]
users = ["admin1", "admin2", "admin3", "admin4", "admin5", "manager1", "manager2", "manager3", "manager4", "manager5",
         "employee1", "employee2", "employee3", "employee4", "employee5", "employee6", "employee7", "employee8",
         "employee9", "employee10", "employee11", "employee12", "employee13", "employee14", "employee15"]
for username in users:
    role = "admin" if "admin" in username else "manager" if "manager" in username else "employee"
    email = f"cz5f9.{username}@inbox.testmail.app"
    password = f"#!{username.capitalize()}Pass$"
    user, created = CustomUser.objects.get_or_create(username=username, defaults={"email": email, "role": role})
    if created:
        print(f"✅ User created: {username} ({role}) | Email: {email} | Password: {password}")
        user.set_password(password)
        user.save()
    else:
        print(f"⚠️ User {username} already exists!")


users = list(CustomUser.objects.all())
projects = []
for i in range(1, 16):
    project = Project.objects.create(name=f"Project {i}", description=f"Project description {i}", owner=random.choice(users))
    projects.append(project)
    print(f"✅ Project created: {project.name}")


projects = list(Project.objects.all())
task = Task()
if not projects:
    print("❌ Error: No projects available. First create projects.")
else:
    statuses = [Task.Status.PENDING, Task.Status.IN_PROGRESS, Task.Status.COMPLETED]
    priorities = [Task.Priority.LOW, Task.Priority.MEDIUM, Task.Priority.HIGH]
    for i in range(1, 71):
        project = random.choice(projects)
        assigned_to = random.sample(users, k=random.randint(1, min(3, len(users))))
        created_by = random.choice(users)
        deadline = now() + timedelta(days=random.randint(1, 30))
        task = Task.objects.create(
            title=f"Task {i}",
            description=f"Task description {i}",
            project=project,
            created_by=created_by,
            modified_by=created_by,
            status=random.choice(statuses),
            priority=random.choice(priorities),
            deadline=deadline,
        )
        task.assigned_to.set(assigned_to)
        print(f"✅ Task created: {task.title} | Project: {project.name} | Priority: {task.priority} | "
              f"Status: {task.status} | Deadline: {task.deadline.strftime('%Y-%m-%d')} | "
              f"Assignees: {', '.join([u.username for u in assigned_to])}")
