"""Pure chess rules — no Django in here.

A board is a plain dict mapping (file, rank) tuples (both 0-7) to
(piece_type, color) tuples, e.g. {(4, 0): ("K", "W")}. Views build it
from GamePiece rows via Game.board() and hand it to these functions.

Not implemented yet: castling, en passant, choice of promotion piece
(pawns auto-promote to queen in the view layer).
"""

WHITE, BLACK = "W", "B"
PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING = "P", "N", "B", "R", "Q", "K"

SLIDING_DIRECTIONS = {
    ROOK: [(1, 0), (-1, 0), (0, 1), (0, -1)],
    BISHOP: [(1, 1), (1, -1), (-1, 1), (-1, -1)],
}
SLIDING_DIRECTIONS[QUEEN] = SLIDING_DIRECTIONS[ROOK] + SLIDING_DIRECTIONS[BISHOP]

KNIGHT_JUMPS = [(1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2)]
KING_STEPS = SLIDING_DIRECTIONS[QUEEN]


def on_board(square):
    file, rank = square
    return 0 <= file <= 7 and 0 <= rank <= 7


def pseudo_moves(board, src):
    """Squares the piece at src can move to, ignoring whether the move
    would leave its own king in check."""
    piece_type, color = board[src]
    file, rank = src
    moves = []

    if piece_type == PAWN:
        step = 1 if color == WHITE else -1
        start_rank = 1 if color == WHITE else 6
        one_ahead = (file, rank + step)
        if on_board(one_ahead) and one_ahead not in board:
            moves.append(one_ahead)
            two_ahead = (file, rank + 2 * step)
            if rank == start_rank and two_ahead not in board:
                moves.append(two_ahead)
        for dfile in (-1, 1):
            capture = (file + dfile, rank + step)
            if on_board(capture) and capture in board and board[capture][1] != color:
                moves.append(capture)

    elif piece_type == KNIGHT:
        for dfile, drank in KNIGHT_JUMPS:
            dst = (file + dfile, rank + drank)
            if on_board(dst) and (dst not in board or board[dst][1] != color):
                moves.append(dst)

    elif piece_type == KING:
        for dfile, drank in KING_STEPS:
            dst = (file + dfile, rank + drank)
            if on_board(dst) and (dst not in board or board[dst][1] != color):
                moves.append(dst)

    else:  # rook, bishop, queen slide until they hit something
        for dfile, drank in SLIDING_DIRECTIONS[piece_type]:
            dst = (file + dfile, rank + drank)
            while on_board(dst):
                if dst in board:
                    if board[dst][1] != color:
                        moves.append(dst)
                    break
                moves.append(dst)
                dst = (dst[0] + dfile, dst[1] + drank)

    return moves


def is_in_check(board, color):
    king_square = next(
        (sq for sq, (pt, c) in board.items() if pt == KING and c == color),
        None,
    )
    if king_square is None:
        return False
    return any(
        king_square in pseudo_moves(board, sq)
        for sq, (_, c) in board.items()
        if c != color
    )


def legal_moves(board, src):
    """Pseudo-moves minus any that leave the mover's own king in check."""
    piece_type, color = board[src]
    result = []
    for dst in pseudo_moves(board, src):
        next_board = dict(board)
        del next_board[src]
        next_board[dst] = (piece_type, color)
        if not is_in_check(next_board, color):
            result.append(dst)
    return result


def has_legal_move(board, color):
    return any(
        legal_moves(board, sq)
        for sq, (_, c) in board.items()
        if c == color
    )
