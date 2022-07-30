import json
import logging

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.functional import cached_property


ACTIONS = {
    "user.password.reset": "Password reset email was sent.",
    "user.token.reset": "API token was reset",
}


class ActivityLog(models.Model):
    user = models.ForeignKey(
        to="core.User",
        on_delete=models.PROTECT,
        related_name="log_entries",
        null=True,
        blank=True,
    )
    content_type = models.ForeignKey(to=ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField(db_index=True)
    content_object = GenericForeignKey("content_type", "object_id")
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    action_type = models.CharField(max_length=200)
    data = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ("-timestamp",)

    def __str__(self):
        """Custom __str__ to help with debugging."""
        user = getattr(self.user, "name", "None")
        return f"ActivityLog(user={user}, content_object={self.content_object}, action_type={self.action_type})"

    @cached_property
    def json_data(self):
        if self.data:
            return json.loads(self.data)
        return {}

    def display(self):
        action = ACTIONS.get(self.action_type)

        if action:
            return action
        logger = logging.getLogger(__name__)
        logger.warning(f'Unknown log action "{self.action_type}".')
        return self.action_type
