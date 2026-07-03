# ♞ Chess

A real-time multiplayer chess web app built with Django. Play locally on
one screen, invite a friend by link, join an open challenge, or hit
quick-match and get paired automatically — moves appear on your
opponent's board instantly over WebSockets.

## Features

- **Full chess rules engine** in pure Python (`core/rules.py`): legal
  move generation for every piece, check, checkmate, stalemate, pins,
  castling with all four classical conditions, pawn promotion.
- **Three ways to play online**: share a game link, join from the
  open-challenges lobby, or quick-match against the first available
  opponent.
- **Local (hotseat) mode**: both players on one screen, no account
  needed.
- **Live sync**: Django Channels + Redis push every move (and joins,
  checkmates, promotions) to all connected browsers — no refresh.
- **Server-side enforcement**: seats, turns, and move legality are all
  validated on the server; the UI can't cheat.
- **Full move history** stored per game, including captures, castling,
  and promotions.

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Django 6 (ASGI via daphne) |
| Realtime | Django Channels + Redis channel layer |
| Database | PostgreSQL 16 |
| Frontend | Server-rendered templates + vanilla JS, CSS grid board, Unicode pieces — zero frontend dependencies |

## Getting started

Requires Python 3.13+, Docker, and Git.

```bash
git clone git@github.com:Osama-A-Abbas/chess-game.git
cd chess-game

# database + websocket broker (persistent dev containers)
docker run -d --name chess-postgres --restart unless-stopped -p 5433:5432 \
  -e POSTGRES_DB=chess_game -e POSTGRES_USER=chess -e POSTGRES_PASSWORD=chess_dev_pw \
  -v chess_pg_data:/var/lib/postgresql/data postgres:16-alpine
docker run -d --name chess-redis --restart unless-stopped -p 6380:6379 redis:7-alpine

# python environment
python -m venv venv
venv/bin/pip install -r requirements.txt

# run
cd chess_game
../venv/bin/python manage.py migrate
../venv/bin/python manage.py runserver 127.0.0.1:8471
```

Open <http://127.0.0.1:8471/>, sign up, and play. For a second player,
use another browser (or a private window — tabs share the login), or
another device on your LAN (see
[docs/portfowarding-control.md](docs/portfowarding-control.md)).

### Configuration

All settings have dev defaults and can be overridden with environment
variables: `CHESS_DB_NAME`, `CHESS_DB_USER`, `CHESS_DB_PASSWORD`,
`CHESS_DB_HOST`, `CHESS_DB_PORT`, `CHESS_REDIS_HOST`,
`CHESS_REDIS_PORT`, `CHESS_ALLOWED_HOSTS`, `CHESS_SECRET_KEY`.

### Tests

```bash
cd chess_game
../venv/bin/python manage.py test core live
```

## Project layout

```
chess_game/
├── chess_game/        # Django project (settings, ASGI/WS routing)
├── core/              # the chess domain
│   ├── models/        # Game, GamePiece, Move
│   ├── rules.py       # pure-Python rules engine (no Django imports)
│   ├── views.py       # pages + JSON move API
│   └── templates/     # board UI, lobby, auth pages
└── live/              # realtime module
    ├── consumers.py   # game-sync + matchmaking WebSocket consumers
    ├── broadcast.py   # channel-layer helpers called from views
    └── models.py      # quick-match queue
```

The design premise: **squares don't exist in the database.** A board is
derived entirely from the positions of its pieces — a game is one row
plus up to 32 piece rows plus its move history. `core/rules.py` operates
on a plain `{(file, rank): (piece_type, color)}` dict and knows nothing
about Django, which keeps the chess logic independently testable.

## Roadmap

- En passant and underpromotion (the two remaining rules)
- Draw detection: threefold repetition, fifty-move rule, insufficient material
- ELO ratings and rating-based matchmaking
- Game clocks

## Photos:
<img width="1798" height="1272" alt="Screenshot From 2026-07-03 14-50-00" src="https://github.com/user-attachments/assets/f9414591-ae91-49f6-8d80-d9c4f1cbbe44" />

<img width="1798" height="1272" alt="Screenshot From 2026-07-03 14-50-16" src="https://github.com/user-attachments/assets/37bd3348-55f6-4a1d-8284-5d95e6f683cf" />

<img width="1798" height="1272" alt="Screenshot From 2026-07-03 14-51-33" src="https://github.com/user-attachments/assets/3cadd7e3-b5f6-4e0e-b439-24d17247756c" />

<img width="1798" height="1272" alt="Screenshot From 2026-07-03 14-52-46" src="https://github.com/user-attachments/assets/2bcc2225-3360-4639-95b6-fd447bcfb48b" />
