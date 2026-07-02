import json

from django.test import TestCase
from django.urls import reverse

from . import rules
from .models import Color, Game, PieceType


def post_move(client, game, src, dst):
    return client.post(
        reverse("game_move", args=[game.id]),
        json.dumps({"from": {"file": src[0], "rank": src[1]}, "to": {"file": dst[0], "rank": dst[1]}}),
        content_type="application/json",
    )


class GameSetupTests(TestCase):
    def test_new_game_has_full_starting_position(self):
        game = Game.create_with_pieces()
        self.assertEqual(game.pieces.count(), 32)
        board = game.board()
        self.assertEqual(board[(4, 0)], (PieceType.KING, Color.WHITE))
        self.assertEqual(board[(4, 7)], (PieceType.KING, Color.BLACK))
        self.assertEqual(board[(3, 0)], (PieceType.QUEEN, Color.WHITE))
        for file in range(8):
            self.assertEqual(board[(file, 1)], (PieceType.PAWN, Color.WHITE))
            self.assertEqual(board[(file, 6)], (PieceType.PAWN, Color.BLACK))


class RulesTests(TestCase):
    def test_pawn_can_single_or_double_step_from_start(self):
        board = Game.create_with_pieces().board()
        self.assertCountEqual(rules.legal_moves(board, (4, 1)), [(4, 2), (4, 3)])

    def test_rook_blocked_by_own_pawns_at_start(self):
        board = Game.create_with_pieces().board()
        self.assertEqual(rules.legal_moves(board, (0, 0)), [])

    def test_knight_can_jump_over_pawns(self):
        board = Game.create_with_pieces().board()
        self.assertCountEqual(rules.legal_moves(board, (1, 0)), [(0, 2), (2, 2)])

    def test_pinned_piece_cannot_move(self):
        # White king e1, white rook e2 pinned by black rook e8.
        board = {
            (4, 0): (rules.KING, rules.WHITE),
            (4, 1): (rules.ROOK, rules.WHITE),
            (4, 7): (rules.ROOK, rules.BLACK),
            (0, 7): (rules.KING, rules.BLACK),
        }
        # The pinned rook may only move along the e-file (staying between king and attacker).
        for dst in rules.legal_moves(board, (4, 1)):
            self.assertEqual(dst[0], 4)

    def test_king_cannot_move_into_check(self):
        board = {
            (4, 0): (rules.KING, rules.WHITE),
            (5, 7): (rules.ROOK, rules.BLACK),
            (0, 7): (rules.KING, rules.BLACK),
        }
        self.assertNotIn((5, 0), rules.legal_moves(board, (4, 0)))
        self.assertNotIn((5, 1), rules.legal_moves(board, (4, 0)))


class MoveEndpointTests(TestCase):
    def setUp(self):
        self.game = Game.create_with_pieces()

    def test_legal_opening_move_succeeds(self):
        response = post_move(self.client, self.game, (4, 1), (4, 3))  # e2-e4
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["turn"], Color.BLACK)
        self.assertIn({"file": 4, "rank": 3, "type": "P", "color": "W"}, data["pieces"])

    def test_illegal_move_is_rejected(self):
        response = post_move(self.client, self.game, (0, 0), (0, 4))  # rook through own pawn
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "Illegal move.")

    def test_cannot_move_out_of_turn(self):
        response = post_move(self.client, self.game, (4, 6), (4, 4))  # black first
        self.assertEqual(response.status_code, 400)

    def test_capture_marks_piece_captured(self):
        post_move(self.client, self.game, (4, 1), (4, 3))  # e4
        post_move(self.client, self.game, (3, 6), (3, 4))  # d5
        response = post_move(self.client, self.game, (4, 3), (3, 4))  # exd5
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.game.pieces.filter(is_captured=True).count(), 1)

    def test_fools_mate_ends_in_checkmate(self):
        post_move(self.client, self.game, (5, 1), (5, 2))  # f3
        post_move(self.client, self.game, (4, 6), (4, 4))  # e5
        post_move(self.client, self.game, (6, 1), (6, 3))  # g4
        response = post_move(self.client, self.game, (3, 7), (7, 3))  # Qh4#
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], Game.Status.CHECKMATE)
        self.assertEqual(data["winner"], Color.BLACK)
        # No further moves allowed.
        response = post_move(self.client, self.game, (4, 1), (4, 3))
        self.assertEqual(response.status_code, 400)

    def test_pawn_promotes_to_queen(self):
        game = Game.objects.create()
        game.pieces.create(piece_type=PieceType.KING, color=Color.WHITE, file=0, rank=0)
        game.pieces.create(piece_type=PieceType.KING, color=Color.BLACK, file=7, rank=7)
        pawn = game.pieces.create(piece_type=PieceType.PAWN, color=Color.WHITE, file=3, rank=6)
        response = post_move(self.client, game, (3, 6), (3, 7))
        self.assertEqual(response.status_code, 200)
        pawn.refresh_from_db()
        self.assertEqual(pawn.piece_type, PieceType.QUEEN)


class PageTests(TestCase):
    def test_home_lists_and_creates_games(self):
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)
        response = self.client.post(reverse("home"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Game.objects.count(), 1)

    def test_game_page_renders(self):
        game = Game.create_with_pieces()
        response = self.client.get(reverse("game_page", args=[game.id]))
        self.assertContains(response, "board")
