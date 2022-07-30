from django.db import models


class Score(models.Model):
    score = models.PositiveIntegerField()  # no negativity allowed!
    date = models.DateField()
    user = models.ForeignKey(
        to="core.User", related_name="scores", on_delete=models.CASCADE
    )
