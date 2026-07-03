import uuid

from django.conf import settings
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

    # Both null: a local hotseat game — anyone at the board moves both sides.
    # white set, black null: an online game waiting for an opponent.
    white_player = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="games_as_white",
    )
    black_player = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="games_as_black",
    )

    @property
    def is_online(self):
        return self.white_player_id is not None

    @property
    def joinable(self):
        return self.is_online and self.black_player_id is None and self.status == self.Status.ACTIVE

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

    def castling_rights(self):
        """Rights like {"WK", "BQ"} (color + side), derived from history:
        a right survives only if neither the king square nor that rook
        square has ever been the origin or destination of a move."""
        touched = set()
        for frm_f, frm_r, to_f, to_r in self.moves.values_list(
            "from_file", "from_rank", "to_file", "to_rank"
        ):
            touched.add((frm_f, frm_r))
            touched.add((to_f, to_r))
        board = self.board()
        rights = set()
        for color, rank in ((Color.WHITE, 0), (Color.BLACK, 7)):
            if (4, rank) in touched or board.get((4, rank)) != (PieceType.KING, color):
                continue
            if (7, rank) not in touched and board.get((7, rank)) == (PieceType.ROOK, color):
                rights.add(color + "K")
            if (0, rank) not in touched and board.get((0, rank)) == (PieceType.ROOK, color):
                rights.add(color + "Q")
        return rights
