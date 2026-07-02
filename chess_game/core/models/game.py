import uuid

from django.db import models

from .piece import Color, GamePiece, PieceType

BACK_RANK = [
    PieceType.ROOK,
    PieceType.KNIGHT,
    PieceType.BISHOP,
    PieceType.QUEEN,
    PieceType.KING,
    PieceType.BISHOP,
    PieceType.KNIGHT,
    PieceType.ROOK,
]


class Game(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "A", "Active"
        CHECKMATE = "M", "Checkmate"
        STALEMATE = "S", "Stalemate"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    turn = models.CharField(max_length=1, choices=Color.choices, default=Color.WHITE)
    status = models.CharField(max_length=1, choices=Status.choices, default=Status.ACTIVE)
    winner = models.CharField(max_length=1, choices=Color.choices, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Game {self.id} ({self.get_status_display()})"

    @classmethod
    def create_with_pieces(cls):
        """Create a game with all 32 pieces in their starting positions."""
        game = cls.objects.create()
        pieces = []
        for file, piece_type in enumerate(BACK_RANK):
            pieces.append(GamePiece(game=game, piece_type=piece_type, color=Color.WHITE, file=file, rank=0))
            pieces.append(GamePiece(game=game, piece_type=piece_type, color=Color.BLACK, file=file, rank=7))
        for file in range(8):
            pieces.append(GamePiece(game=game, piece_type=PieceType.PAWN, color=Color.WHITE, file=file, rank=1))
            pieces.append(GamePiece(game=game, piece_type=PieceType.PAWN, color=Color.BLACK, file=file, rank=6))
        GamePiece.objects.bulk_create(pieces)
        return game

    def board(self):
        """The live position as {(file, rank): (piece_type, color)} — the shape rules.py works with."""
        return {
            (p.file, p.rank): (p.piece_type, p.color)
            for p in self.pieces.filter(is_captured=False)
        }
