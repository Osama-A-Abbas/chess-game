from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST

from core.models import Game

from .broadcast import notify_match_found
from .models import QueueEntry


@login_required
@require_POST
def find_match(request):
    """Pair with the longest-waiting queued player, or join the queue.
    The row lock (skip_locked) makes two simultaneous callers grab
    different queue entries instead of both pairing with the same one."""
    with transaction.atomic():
        entry = (
            QueueEntry.objects.select_for_update(skip_locked=True)
            .exclude(user=request.user)
            .order_by("created_at")
            .first()
        )
        if entry is None:
            QueueEntry.objects.get_or_create(user=request.user)
            return JsonResponse({"queued": True})
        opponent = entry.user
        entry.delete()
        QueueEntry.objects.filter(user=request.user).delete()
        game = Game.create_with_pieces()
        game.white_player = opponent  # the one who waited gets White
        game.black_player = request.user
        game.save()
    game_url = reverse("game_page", args=[game.id])
    notify_match_found(opponent.id, game_url)
    return JsonResponse({"matched": True, "game_url": game_url})


@login_required
@require_POST
def cancel_match(request):
    QueueEntry.objects.filter(user=request.user).delete()
    return JsonResponse({"cancelled": True})
