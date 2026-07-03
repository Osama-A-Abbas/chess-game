# LAN Access Control (Port Forwarding)

How to enable or disable access to the chess server from other devices
on your local network — and what each layer actually does.

> **Terminology note:** what we toggle here is technically *LAN access*
> (which network interface the server listens on). Real *port
> forwarding* is a router setting that exposes your machine to the
> internet — see the last section. For playing from your phone or
> another laptop on the same Wi-Fi, LAN access is all you need.

## The two layers

Access from another device requires **both** layers to allow it. Locking
either one disables outside access.

| Layer | Setting | Allows LAN | Blocks LAN |
|---|---|---|---|
| 1. Bind address | `runserver <address>:8471` | `0.0.0.0` | `127.0.0.1` |
| 2. Django host check | `CHESS_ALLOWED_HOSTS` env var | `*` (current default) | `localhost,127.0.0.1` |

### Layer 1 — bind address (the main switch)

The address you pass to `runserver` decides which network interface the
server listens on:

- `127.0.0.1:8471` — loopback only. The OS itself refuses connections
  from any other device; nothing else can even reach Django. **This is
  the "disabled" state.**
- `0.0.0.0:8471` — every interface, including your Wi-Fi/Ethernet IP.
  Other devices can connect. **This is the "enabled" state.**

### Layer 2 — Django's host check

Even when reachable, Django rejects requests whose `Host` header isn't
in `ALLOWED_HOSTS` (HTTP 400). The same list gates WebSocket origins,
so if you lock this down but keep `0.0.0.0`, LAN devices get errors
rather than a working board. It's configured in
`chess_game/chess_game/settings.py` via the `CHESS_ALLOWED_HOSTS`
environment variable; the dev default is `*` (allow any host header).

## Disable LAN access (localhost only)

```bash
# stop whatever server is running
pkill -f "manage.py runserver"

# start bound to loopback only
cd ~/Desktop/projects/chess_game/chess_game
../venv/bin/python manage.py runserver 127.0.0.1:8471
```

Verify it is off — from the same machine:

```bash
ss -tlnp | grep 8471
# LISTEN ... 127.0.0.1:8471   ← loopback only: disabled
# LISTEN ... 0.0.0.0:8471     ← all interfaces: enabled

curl -s -o /dev/null -w "%{http_code}\n" http://$(hostname -I | awk '{print $1}'):8471/
# "Connection refused" / non-200  ← disabled
# 200                            ← still enabled
```

## Enable LAN access

```bash
pkill -f "manage.py runserver"
cd ~/Desktop/projects/chess_game/chess_game
../venv/bin/python manage.py runserver 0.0.0.0:8471
```

Then on the other device, open `http://<your-lan-ip>:8471/`. Find your
LAN IP with:

```bash
hostname -I | awk '{print $1}'
```

The IP comes from DHCP and can change after a reboot or network
reconnect — re-check it if the other device suddenly can't connect.

### Optional hardening while enabled

Instead of the `*` default, restrict Django to exactly the hosts you
expect (localhost plus your current LAN IP):

```bash
CHESS_ALLOWED_HOSTS="localhost,127.0.0.1,10.115.21.36" \
    ../venv/bin/python manage.py runserver 0.0.0.0:8471
```

## Firewall (Fedora)

Fedora Workstation's default firewalld zone already allows incoming TCP
on ports 1025–65535, so port 8471 needs no firewall change. If you ever
tighten that zone, re-open the port with:

```bash
sudo firewall-cmd --add-port=8471/tcp            # until reboot
sudo firewall-cmd --add-port=8471/tcp --permanent && sudo firewall-cmd --reload
```

And to close it again:

```bash
sudo firewall-cmd --remove-port=8471/tcp --permanent && sudo firewall-cmd --reload
```

## Real port forwarding (internet play) — do not do this casually

Exposing the dev server to the internet means configuring your router
to forward an external port to `<your-lan-ip>:8471`. Don't — the
project currently runs with `DEBUG=True`, a hardcoded `SECRET_KEY`, and
the Django development server, all of which are unsafe on the open
internet. If you want to play with someone outside your network:

- **Tailscale** (recommended): free mesh VPN; install it on both
  devices and they see each other on a private network — no router
  changes, nothing exposed publicly.
- **Proper deployment**: `DEBUG=False`, secret key from the
  environment, explicit `CHESS_ALLOWED_HOSTS`, daphne/gunicorn behind
  a reverse proxy with HTTPS. Worth doing when the game is ready to
  share widely.
