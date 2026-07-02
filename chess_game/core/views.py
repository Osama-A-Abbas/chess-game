import json

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from . import rules
from .models import Color, Game, Move, PieceType


def game_state(game):
    """Everything the frontend needs to draw the game, as JSON-able data."""
    board = game.board()
    return {
        "id": str(game.id),
        "turn": game.turn,
        "status": game.status,
        "winner": game.winner,
        "in_check": game.status == Game.Status.ACTIVE and rules.is_in_check(board, game.turn),
        "pieces": [
            {"file": f, "rank": r, "type": pt, "color": c}
            for (f, r), (pt, c) in board.items()
        ],
        "moves": [str(m) for m in game.moves.all()],
    }


def home(request):
    if request.method == "POST":
        game = Game.create_with_pieces()
        return redirect("game_page", game_id=game.id)
    games = Game.objects.order_by("-created_at")[:20]
    return render(request, "core/home.html", {"games": games})


@ensure_csrf_cookie
def game_page(request, game_id):
    game = get_object_or_404(Game, id=game_id)
    return render(request, "core/game.html", {"game": game})


@require_GET
def state(request, game_id):
    game = get_object_or_404(Game, id=game_id)
    return JsonResponse(game_state(game))


@require_GET
def legal(request, game_id):
    """Legal destinations for the piece on ?file=&rank= — used for highlighting."""
    game = get_object_or_404(Game, id=game_id)
    try:
        src = (int(request.GET["file"]), int(request.GET["rank"]))
    except (KeyError, ValueError):
        return JsonResponse({"error": "file and rank query params required"}, status=400)
    board = game.board()
    if game.status != Game.Status.ACTIVE or src not in board or board[src][1] != game.turn:
        return JsonResponse({"moves": []})
    return JsonResponse(
        {"moves": [{"file": f, "rank": r} for f, r in rules.legal_moves(board, src)]}
    )


@require_POST
@transaction.atomic
def move(request, game_id):
    game = get_object_or_404(Game.objects.select_for_update(), id=game_id)
    if game.status != Game.Status.ACTIVE:
        return JsonResponse({"error": "Game is over."}, status=400)
    try:
        data = json.loads(request.body)
        src = (int(data["from"]["file"]), int(data["from"]["rank"]))
        dst = (int(data["to"]["file"]), int(data["to"]["rank"]))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return JsonResponse({"error": "Bad move payload."}, status=400)

    board = game.board()
    if src not in board:
        return JsonResponse({"error": "No piece on that square."}, status=400)
    if board[src][1] != game.turn:
        return JsonResponse({"error": "It is not that color's turn."}, status=400)
    if dst not in rules.legal_moves(board, src):
        return JsonResponse({"error": "Illegal move."}, status=400)

    piece = game.pieces.get(file=src[0], rank=src[1], is_captured=False)
    moved_type = piece.piece_type

    captured = game.pieces.filter(file=dst[0], rank=dst[1], is_captured=False).first()
    if captured:
        captured.is_captured = True
        captured.save()

    piece.file, piece.rank = dst
    promoted = piece.piece_type == PieceType.PAWN and piece.rank in (0, 7)
    if promoted:
        piece.piece_type = PieceType.QUEEN
    piece.save()

    Move.objects.create(
        game=game,
        number=game.moves.count() + 1,
        color=piece.color,
        piece_type=moved_type,
        from_file=src[0],
        from_rank=src[1],
        to_file=dst[0],
        to_rank=dst[1],
        captured_type=captured.piece_type if captured else "",
        promoted=promoted,
    )

    opponent = Color.BLACK if game.turn == Color.WHITE else Color.WHITE
    new_board = game.board()
    if not rules.has_legal_move(new_board, opponent):
        if rules.is_in_check(new_board, opponent):
            game.status = Game.Status.CHECKMATE
            game.winner = game.turn
        else:
            game.status = Game.Status.STALEMATE
    game.turn = opponent
    game.save()

    return JsonResponse(game_state(game))
