from django.db import models
import os

import json
import random
from contextlib import suppress
from hashlib import md5
from urllib.parse import urljoin

import pytz
from django.conf import settings
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.contrib.contenttypes.models import ContentType
from django.db import models, transaction
from django.db.models import Q
from django.utils.crypto import get_random_string
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django.utils.translation import override
from django_scopes import scopes_disabled
from rest_framework.authtoken.models import Token


def path_with_hash(name):
    dir_name, file_name = os.path.split(name)
    file_root, file_ext = os.path.splitext(file_name)
    random = get_random_string(7)
    return os.path.join(dir_name, f"{file_root}_{random}{file_ext}")


def avatar_path(instance, filename):
    return f"avatars/{path_with_hash(filename)}"


class FileCleanupMixin:
    """Deletes all uploaded files when object is deleted."""

    def _delete_files(self):
        file_attributes = [
            field.name
            for field in self._meta.fields
            if isinstance(field, models.FileField)
        ]
        for field in file_attributes:
            value = getattr(self, field, None)
            if value:
                with suppress(Exception):
                    value.delete(save=False)

    def delete(self, *args, **kwargs):
        self._delete_files()
        return super().delete(*args, **kwargs)


class UserManager(BaseUserManager):
    """The user manager class."""

    def create_user(self, password: str = None, **kwargs):
        user = self.model(**kwargs)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, password: str, **kwargs):
        user = self.create_user(password=password, **kwargs)
        user.is_superuser = True
        user.is_staff = True
        user.save()
        return user


class User(FileCleanupMixin, AbstractBaseUser):

    EMAIL_FIELD = "email"
    USERNAME_FIELD = "email"

    objects = UserManager()

    name = models.CharField(
        max_length=120,
        verbose_name=_("Name"),
        help_text=_(
            "Please enter the name you wish to be displayed publicly. You can always change it later."
        ),
    )
    email = models.EmailField(
        unique=True,
        verbose_name=_("E-mail"),
        help_text=_(
            "Your email address will only be used to identify you when you log in, and to send you password reset emails when you request them."
        ),
    )
    is_active = models.BooleanField(
        default=True, help_text="Inactive users are not allowed to log in."
    )
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    # not in use atm
    locale = models.CharField(
        max_length=32,
        default=settings.LANGUAGE_CODE,
        choices=settings.LANGUAGES,
        verbose_name=_("Preferred language"),
    )
    # not in use atm
    timezone = models.CharField(
        choices=[(tz, tz) for tz in pytz.common_timezones], max_length=30, default="UTC"
    )
    avatar = models.ImageField(
        null=True,
        blank=True,
        verbose_name=_("Profile picture"),
        help_text=_("If possible, upload an image that is least 120 pixels wide."),
        upload_to=avatar_path,
    )
    pw_reset_token = models.CharField(
        null=True, max_length=160, verbose_name="Password reset token"
    )
    pw_reset_time = models.DateTimeField(null=True, verbose_name="Password reset time")

    locked = models.BooleanField(
        verbose_name=_("Lock account"),
        help_text=_("Posts by locked accounts will only be visible to their followers, and you can approve follow requests first."),
        default=False,
    )
    app_token = models.CharField(
        null=True, max_length=160, verbose_name="App token",
        help_text=_("The secret token used by scripts and apps to post. Resetting it generates a new token, and the old token won't work anymore."),
    )

    def __str__(self) -> str:
        """For public consumption, used in auto generated drop-downs etc."""
        return self.name or str(_("Unnamed user"))

    def get_display_name(self) -> str:
        """Returns a user's name or 'Unnamed user'."""
        return str(self)

    def save(self, *args, **kwargs):
        self.email = self.email.lower().strip()
        return super().save(*args, **kwargs)

    def log_action(self, action: str, data: dict = None, user=None):
        """Create a log entry for this user.
        """
        from .log import ActivityLog

        if data:
            data = json.dumps(data)

        ActivityLog.objects.create(
            user=user or self,
            content_object=self,
            action_type=action,
            data=data,
        )

    def logged_actions(self):
        """Returns all log entries that were made about this user."""
        from .log import ActivityLog

        return ActivityLog.objects.filter(
            content_type=ContentType.objects.get_for_model(type(self)),
            object_id=self.pk,
        )

    def own_actions(self):
        """Returns all log entries that were made by this user."""
        from .log import ActivityLog

        return ActivityLog.objects.filter(user=self)

    def regenerate_token(self) -> Token:
        """Generates a new API access token, deleting the old one."""
        self.log_action(action="user.token.reset")
        self.app_token = get_random_string(32)
        self.save()
        return self.app_token

    regenerate_token.alters_data = True

    @transaction.atomic
    def reset_password(self, event, user=None, mail_text=None, orga=False):
        self.pw_reset_token = get_random_string(32)
        self.pw_reset_time = now()
        self.save()

        url = build_absolute_uri(
            "auth.recover", kwargs={"token": self.pw_reset_token}
        )
        context = {
            "name": self.name or "",
            "url": url,
        }
        if not mail_text:
            mail_text = _(
                """Hi {name},

you have requested a new password for your Ankisocial account.
To reset your password, click on the following link:

  {url}

If this wasn\'t you, you can just ignore this email.

All the best,
the Ankisocial robot"""
            )

        # TODO actually send email
        subject=_("Password recovery")
        self.log_action(action="user.password.reset", person=user)
    reset_password.alters_data = True
