from django.db import models

from .piece import Color, PieceType


class Move(models.Model):
    game = models.ForeignKey("core.Game", on_delete=models.CASCADE, related_name="moves")
    number = models.PositiveIntegerField()  # 1, 2, 3... across both colors
    color = models.CharField(max_length=1, choices=Color.choices)
    piece_type = models.CharField(max_length=1, choices=PieceType.choices)
    from_file = models.PositiveSmallIntegerField()
    from_rank = models.PositiveSmallIntegerField()
    to_file = models.PositiveSmallIntegerField()
    to_rank = models.PositiveSmallIntegerField()
    captured_type = models.CharField(max_length=1, choices=PieceType.choices, blank=True, default="")
    promoted = models.BooleanField(default=False)

    class Meta:
        ordering = ["number"]

    def __str__(self):
        frm = f"{chr(ord('a') + self.from_file)}{self.from_rank + 1}"
        to = f"{chr(ord('a') + self.to_file)}{self.to_rank + 1}"
        return f"{self.number}. {self.piece_type} {frm}-{to}"
