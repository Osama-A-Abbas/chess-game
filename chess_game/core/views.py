import json

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from live.broadcast import broadcast_game_state

from . import rules
from .models import Color, Game, Move, PieceType


def game_state(game):
    """Everything the frontend needs to draw the game, as JSON-able data.
    User-agnostic on purpose: the same payload is broadcast to every
    connected client of the game."""
    board = game.board()
    return {
        "id": str(game.id),
        "turn": game.turn,
        "status": game.status,
        "winner": game.winner,
        "online": game.is_online,
        "white": game.white_player.username if game.white_player else None,
        "black": game.black_player.username if game.black_player else None,
        "in_check": game.status == Game.Status.ACTIVE and rules.is_in_check(board, game.turn),
        "pieces": [
            {"file": f, "rank": r, "type": pt, "color": c}
            for (f, r), (pt, c) in board.items()
        ],
        "moves": [str(m) for m in game.moves.all()],
    }


def home(request):
    if request.method == "POST":
        if request.POST.get("mode") == "online":
            if not request.user.is_authenticated:
                return redirect("login")
            game = Game.create_with_pieces()
            game.white_player = request.user
            game.save()
        else:
            game = Game.create_with_pieces()
        return redirect("game_page", game_id=game.id)

    open_challenges = Game.objects.filter(
        white_player__isnull=False, black_player__isnull=True, status=Game.Status.ACTIVE
    ).exclude(white_player=request.user if request.user.is_authenticated else None
    ).order_by("-created_at")[:20]
    my_games = []
    if request.user.is_authenticated:
        my_games = Game.objects.filter(
            Q(white_player=request.user) | Q(black_player=request.user)
        ).order_by("-created_at")[:20]
    local_games = Game.objects.filter(white_player__isnull=True).order_by("-created_at")[:10]
    return render(request, "core/home.html", {
        "open_challenges": open_challenges,
        "my_games": my_games,
        "local_games": local_games,
    })


def signup(request):
    form = UserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("home")
    return render(request, "registration/signup.html", {"form": form})


@ensure_csrf_cookie
def game_page(request, game_id):
    game = get_object_or_404(Game, id=game_id)
    your_color = ""
    if request.user.is_authenticated:
        if game.white_player_id == request.user.id:
            your_color = Color.WHITE
        elif game.black_player_id == request.user.id:
            your_color = Color.BLACK
    can_join = game.joinable and request.user.is_authenticated and not your_color
    return render(request, "core/game.html", {
        "game": game,
        "your_color": your_color,
        "can_join": can_join,
    })


@login_required
@require_POST
def join_game(request, game_id):
    with transaction.atomic():
        game = get_object_or_404(Game.objects.select_for_update(), id=game_id)
        if not game.joinable or game.white_player_id == request.user.id:
            return redirect("game_page", game_id=game.id)
        game.black_player = request.user
        game.save()
    broadcast_game_state(game.id, game_state(game))
    return redirect("game_page", game_id=game.id)


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
        {
            "moves": [
                {"file": f, "rank": r}
                for f, r in rules.legal_moves(board, src, game.castling_rights())
            ]
        }
    )


@require_POST
@transaction.atomic
def move(request, game_id):
    game = get_object_or_404(Game.objects.select_for_update(), id=game_id)
    if game.status != Game.Status.ACTIVE:
        return JsonResponse({"error": "Game is over."}, status=400)

    if game.is_online:
        if game.black_player_id is None:
            return JsonResponse({"error": "Waiting for an opponent to join."}, status=400)
        seat = game.white_player_id if game.turn == Color.WHITE else game.black_player_id
        if not request.user.is_authenticated or request.user.id != seat:
            return JsonResponse({"error": "It is not your turn."}, status=403)

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
    if dst not in rules.legal_moves(board, src, game.castling_rights()):
        return JsonResponse({"error": "Illegal move."}, status=400)

    piece = game.pieces.get(file=src[0], rank=src[1], is_captured=False)
    moved_type = piece.piece_type

    castled = moved_type == PieceType.KING and abs(dst[0] - src[0]) == 2
    if castled:
        rook_from_file, rook_to_file = (7, 5) if dst[0] == 6 else (0, 3)
        rook = game.pieces.get(file=rook_from_file, rank=src[1], is_captured=False)
        rook.file = rook_to_file
        rook.save()

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
        castled=castled,
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

    payload = game_state(game)
    transaction.on_commit(lambda: broadcast_game_state(game.id, payload))
    return JsonResponse(payload)
