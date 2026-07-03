from django.conf import settings
from django.db import models


class QueueEntry(models.Model):
    """A player waiting in the quick-match queue. OneToOne so clicking
    'find match' twice can't enqueue the same player twice."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} queued at {self.created_at:%H:%M:%S}"
