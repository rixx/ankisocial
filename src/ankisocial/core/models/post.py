from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _


class PostType(models.TextChoices):
    TEXT = "text"
    STREAK = "streak"
    DAY_SUMMARY = "day"
    DAY_CARDS = "day_cards"
    DAX_DURATION = "day_duration"


class Post(models.Model):
    """A post as it appears on the timeline."""

    user = models.ForeignKey(
        to="core.User", related_name="posts", on_delete=models.CASCADE
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    post_type = models.CharField(max_length=10, choices=PostType.choices)
    achievement = models.BooleanField(
        default=False
    )  # basically a "the most I ever got", but difficult as a single flag with composite data (is the card count or the duration the achievement?)

    content_date = models.DateField()  # Which date is the post about?
    content_time_range = models.PositiveIntegerField(
        default=1
    )  # In days, with 1/7/14 etc being good defaults. We'll just call months 30 days and years 365 😬

    # data contains different content depending on the post_type
    # - text: "text"
    # - streak: "days"
    # - day_summary: "cards", "cards_unique" (optional), "duration" (minutes, float)
    # - day_cards: "cards", "cards_unique" (or just either of them)
    # - day_duration: "duration" (minutes, float)
    data = models.JSONField()

    comment = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Comment"),
        help_text=_(
            "Without a comment, your post will still show your stats and your achievements."
        ),
    )

    class Meta:
        ordering = ("-post_date",)

    @cached_property
    def post_main_text(self):
        if self.post_type == PostType.TEXT:
            return self.data.get("text", "")
        if self.post_type == PostType.STREAK:
            return _("{user} reached a streak of {days} days!").format(
                user=self.user, days=self.data["days"]
            )
        # TODO more text variants
        # TODO texts for all the post_type + content_time_range combination


class ReactionType(models.TextChoices):
    WHEE = "whee"
    PARTY = "party"
    COOL = "cool"
    # etc etc


class Reaction(models.Model):
    reaction_type = models.CharField(
        max_length=10, choices=ReactionType.choices, default=ReactionType.WHEE
    )
    user = models.ForeignKey(
        to="core.User", related_name="reactions", on_delete=models.CASCADE
    )
    post = models.ForeignKey(
        to="core.Post", related_name="reactions", on_delete=models.CASCADE
    )
