from django.db import models


class Color(models.TextChoices):
    WHITE = "W", "White"
    BLACK = "B", "Black"


class PieceType(models.TextChoices):
    PAWN = "P", "Pawn"
    KNIGHT = "N", "Knight"
    BISHOP = "B", "Bishop"
    ROOK = "R", "Rook"
    QUEEN = "Q", "Queen"
    KING = "K", "King"


class GamePiece(models.Model):
    game = models.ForeignKey("core.Game", on_delete=models.CASCADE, related_name="pieces")
    piece_type = models.CharField(max_length=1, choices=PieceType.choices)
    color = models.CharField(max_length=1, choices=Color.choices)
    file = models.PositiveSmallIntegerField()  # 0-7 -> columns a-h
    rank = models.PositiveSmallIntegerField()  # 0-7 -> rows 1-8
    is_captured = models.BooleanField(default=False)

    @property
    def square(self):
        return f"{chr(ord('a') + self.file)}{self.rank + 1}"

    def __str__(self):
        return f"{self.get_color_display()} {self.get_piece_type_display()} @ {self.square}"
