from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _


class CustomUser(AbstractUser):
    email = models.EmailField(_('Email address'), unique=True)
    first_name = models.CharField(_('First Name'), max_length=30, blank=True, null=True)
    last_name = models.CharField(_('Last Name'), max_length=30, blank=True, null=True)

    class Role(models.TextChoices):
        SUPERADMIN = 'superadmin', _('Super Administrator')
        ADMIN = 'admin', _('Administrator')
        MANAGER = 'manager', _('Manager')
        EMPLOYEE = 'employee', _('Employee')

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.EMPLOYEE,
        help_text=_('User role in the system'),
    )
    telegram_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        unique=True,
        help_text=_('Telegram ID for notifications'),
    )
    telegram_notifications_enabled = models.BooleanField(
        default=False,
        help_text=_('Enable Telegram notifications'),
    )
    phone_number = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        help_text=_('User phone number (optional)'),
    )
    is_active = models.BooleanField(
        default=True,
        help_text=_('Is the user active'),
    )
    date_of_birth = models.DateField(
        blank=True,
        null=True,
        help_text=_('User date of birth (optional)'),
    )
    avatar = models.ImageField(
        upload_to='avatars/',
        blank=True,
        null=True,
        help_text=_('Profile picture (optional)'),
    )

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')

    def __str__(self):
        return f"{self.username} ({self.get_role_display()}) - {self.email}"

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = self.Role.SUPERADMIN
        super().save(*args, **kwargs)
