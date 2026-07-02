from django.contrib import admin

from .models import Game, GamePiece, Move


class GamePieceInline(admin.TabularInline):
    model = GamePiece
    extra = 0


class MoveInline(admin.TabularInline):
    model = Move
    extra = 0


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ["id", "turn", "status", "winner", "created_at"]
    inlines = [GamePieceInline, MoveInline]


@admin.register(GamePiece)
class GamePieceAdmin(admin.ModelAdmin):
    list_display = ["game", "piece_type", "color", "square", "is_captured"]
    list_filter = ["color", "piece_type", "is_captured"]
