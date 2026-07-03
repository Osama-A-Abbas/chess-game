import json

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from live.models import QueueEntry

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


class CastlingTests(TestCase):
    def bare_board(self, *extra):
        board = {
            (4, 0): (rules.KING, rules.WHITE),
            (7, 0): (rules.ROOK, rules.WHITE),
            (4, 7): (rules.KING, rules.BLACK),
        }
        board.update(extra)
        return board

    def test_kingside_castle_available_with_rights(self):
        moves = rules.legal_moves(self.bare_board(), (4, 0), {"WK"})
        self.assertIn((6, 0), moves)

    def test_no_castle_without_rights(self):
        moves = rules.legal_moves(self.bare_board(), (4, 0), set())
        self.assertNotIn((6, 0), moves)

    def test_no_castle_through_occupied_square(self):
        board = self.bare_board(((5, 0), (rules.BISHOP, rules.WHITE)))
        self.assertNotIn((6, 0), rules.legal_moves(board, (4, 0), {"WK"}))

    def test_no_castle_while_in_check(self):
        board = self.bare_board(((4, 6), (rules.ROOK, rules.BLACK)))
        self.assertNotIn((6, 0), rules.legal_moves(board, (4, 0), {"WK"}))

    def test_no_castle_through_attacked_square(self):
        board = self.bare_board(((5, 6), (rules.ROOK, rules.BLACK)))  # black rook eyes f1
        self.assertNotIn((6, 0), rules.legal_moves(board, (4, 0), {"WK"}))

    def test_rights_lost_after_king_moves(self):
        game = Game.create_with_pieces()
        self.assertEqual(game.castling_rights(), {"WK", "WQ", "BK", "BQ"})
        game.moves.create(
            number=1, color=Color.WHITE, piece_type=PieceType.KING,
            from_file=4, from_rank=0, to_file=4, to_rank=1,
        )
        self.assertEqual(game.castling_rights(), {"BK", "BQ"})

    def test_full_castle_via_endpoint_moves_both_pieces(self):
        game = Game.create_with_pieces()
        post_move(self.client, game, (6, 0), (5, 2))  # Nf3
        post_move(self.client, game, (0, 6), (0, 5))  # a6
        post_move(self.client, game, (4, 1), (4, 2))  # e3
        post_move(self.client, game, (1, 6), (1, 5))  # b6
        post_move(self.client, game, (5, 0), (4, 1))  # Be2
        post_move(self.client, game, (2, 6), (2, 5))  # c6
        response = post_move(self.client, game, (4, 0), (6, 0))  # O-O
        self.assertEqual(response.status_code, 200)
        board = game.board()
        self.assertEqual(board[(6, 0)], (PieceType.KING, Color.WHITE))
        self.assertEqual(board[(5, 0)], (PieceType.ROOK, Color.WHITE))
        self.assertNotIn((4, 0), board)
        self.assertNotIn((7, 0), board)
        self.assertTrue(game.moves.get(number=7).castled)


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


class OnlineGameTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pw")
        self.bob = User.objects.create_user("bob", password="pw")
        self.client.force_login(self.alice)
        self.client.post(reverse("home"), {"mode": "online"})
        self.game = Game.objects.get()

    def bob_client(self, join=True):
        client = Client()
        client.force_login(self.bob)
        if join:
            client.post(reverse("game_join", args=[self.game.id]))
            self.game.refresh_from_db()
        return client

    def test_creator_is_seated_as_white(self):
        self.assertEqual(self.game.white_player, self.alice)
        self.assertIsNone(self.game.black_player)
        self.assertTrue(self.game.joinable)

    def test_cannot_move_before_opponent_joins(self):
        response = post_move(self.client, self.game, (4, 1), (4, 3))
        self.assertEqual(response.status_code, 400)
        self.assertIn("Waiting for an opponent", response.json()["error"])

    def test_creator_cannot_join_own_game(self):
        self.client.post(reverse("game_join", args=[self.game.id]))
        self.game.refresh_from_db()
        self.assertIsNone(self.game.black_player)

    def test_join_and_alternate_moves(self):
        bob = self.bob_client()
        self.assertEqual(self.game.black_player, self.bob)
        self.assertEqual(post_move(self.client, self.game, (4, 1), (4, 3)).status_code, 200)
        self.assertEqual(post_move(bob, self.game, (4, 6), (4, 4)).status_code, 200)

    def test_cannot_move_opponents_pieces(self):
        bob = self.bob_client()
        response = post_move(bob, self.game, (4, 1), (4, 3))  # bob moving white
        self.assertEqual(response.status_code, 403)

    def test_anonymous_spectator_cannot_move(self):
        self.bob_client()
        response = post_move(Client(), self.game, (4, 1), (4, 3))
        self.assertEqual(response.status_code, 403)

    def test_second_joiner_is_rejected(self):
        self.bob_client()
        charlie = Client()
        charlie.force_login(User.objects.create_user("charlie", password="pw"))
        charlie.post(reverse("game_join", args=[self.game.id]))
        self.game.refresh_from_db()
        self.assertEqual(self.game.black_player, self.bob)


class MatchmakingTests(TestCase):
    def setUp(self):
        self.alice_client = Client()
        self.alice_client.force_login(User.objects.create_user("alice", password="pw"))
        self.bob_client = Client()
        self.bob_client.force_login(User.objects.create_user("bob", password="pw"))

    def test_first_caller_queues_second_gets_matched(self):
        first = self.alice_client.post(reverse("find_match")).json()
        self.assertEqual(first, {"queued": True})
        second = self.bob_client.post(reverse("find_match")).json()
        self.assertTrue(second["matched"])
        game = Game.objects.get()
        self.assertEqual(game.white_player.username, "alice")
        self.assertEqual(game.black_player.username, "bob")
        self.assertEqual(QueueEntry.objects.count(), 0)

    def test_cancel_leaves_queue(self):
        self.alice_client.post(reverse("find_match"))
        self.alice_client.post(reverse("cancel_match"))
        result = self.bob_client.post(reverse("find_match")).json()
        self.assertEqual(result, {"queued": True})

    def test_queueing_twice_is_idempotent(self):
        self.alice_client.post(reverse("find_match"))
        self.alice_client.post(reverse("find_match"))
        self.assertEqual(QueueEntry.objects.count(), 1)

    def test_anonymous_cannot_queue(self):
        response = Client().post(reverse("find_match"))
        self.assertEqual(response.status_code, 302)  # redirected to login


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
