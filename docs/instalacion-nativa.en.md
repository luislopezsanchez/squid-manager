# Native installation (without Docker)

**[Español](instalacion-nativa.md) · English · [Português](instalacion-nativa.pt.md)**

SquidManager can be deployed without Docker, with Squid, the panel, PostgreSQL
and nginx running as system services. It is the alternative to containers, not a
complement: on a given machine you use one **or** the other.

> The Spanish version, [instalacion-nativa.md](instalacion-nativa.md), is the
> source of truth. If they disagree, the Spanish one is right.

Who it makes sense for:

- Networks where internal policy does not allow Docker.
- A machine that already acts as a proxy, and where adding a container runtime
  means adding a moving part nobody asked for.
- Appliances or small machines, where skipping the container layer is
  noticeable.

## Requirements

- Ubuntu 22.04/24.04 or Debian 12, x86_64.
- Root access.
- Internet access to download packages and clone the repository.

> ⚠️ **Ubuntu 26.04 is not supported yet.** It ships Python 3.14 by
> default, and `psycopg[binary]` and `pydantic-core` don't have prebuilt
> wheels for that version (`pydantic-core` doesn't even build from source:
> its Rust toolchain —PyO3 0.22— doesn't support Python 3.14 at all). Step
> 8 of the installer fails with `ERROR: Could not find a version that
> satisfies the requirement psycopg-binary==3.2.3`. Use Ubuntu 24.04 or
> Debian 12 until the Python ecosystem catches up.

## Installing

```bash
wget https://raw.githubusercontent.com/luislopezsanchez/squid-manager/main/install-nativo.sh
less install-nativo.sh          # read what it is going to do to your server
chmod +x install-nativo.sh
sudo ./install-nativo.sh
```

When it finishes it prints the panel URL and the initial password for `admin`,
which must be changed on first access.

It can be tuned with environment variables:

```bash
WEB_PORT=8080 PROXY_PORT=3130 sudo -E ./install-nativo.sh
```

| Variable | Default | What it is |
|---|---|---|
| `WEB_PORT` | `3000` | Panel port |
| `PROXY_PORT` | `3128` | Proxy port |
| `API_PORT` | `8000` | Internal API port (listens on localhost only) |
| `INSTALL_DIR` | `/opt/squid-manager` | Where the code lives |
| `APP_USER` | `squidmgr` | User the panel runs as |
| `BRANCH` | `main` | Repository branch to deploy |

## Freshly installed, the proxy lets nobody through

This is deliberate, and worth knowing before you test it.

There are a few seconds between Squid starting up and a real configuration
existing. The configuration covering that gap **denies everything except
`localhost`**: if it allowed the local network, anyone in the private range
could use the proxy with no credentials during that window — and for however
long it took someone to open the panel.

The panel replaces that bootstrap with the definitive, authenticated
configuration as soon as the backend comes up. The installer checks this before
finishing and warns if it did not happen.

The practical consequence: **nobody browses on a fresh install**, because there
are no proxy users yet. Create the first one in the panel, under *Users → New
user*, and from then on the proxy asks for a username and password.

```bash
# no credentials: 407, which is the correct answer
curl -x http://SERVER_IP:3128 -o /dev/null -w "%{http_code}\n" http://example.com
```

## What it installs, and why that way

### `squid-openssl`, not `squid`

Debian and Ubuntu package Squid twice. The plain `squid` package is the
**GnuTLS** flavour: no `--with-openssl`, no `--enable-ssl-crtd`, and no
`security_file_certgen`. With it, the panel's SSL Bump cannot work, and the
failure shows up much later and with no apparent connection to the cause.

`squid-openssl` does bring everything the project needs — OpenSSL, ssl-crtd,
delay pools, NCSA and LDAP basic authentication, 65536 file descriptors — so
**nothing has to be compiled**. The installer checks this explicitly and aborts
if the binary it finds is not built with OpenSSL.

Both packages install the same `/usr/sbin/squid` binary and cannot coexist:
installing one removes the other.

### Privileges: a dedicated user and three commands

The panel **does not run as root**. The `squidmgr` user is created with `proxy`
as its primary group, plus a sudoers file with three literal commands, no
wildcards:

```
squidmgr ALL=(root) NOPASSWD: /usr/sbin/squid -f /etc/squid/squid.conf -k reconfigure
squidmgr ALL=(root) NOPASSWD: /usr/sbin/squid -k parse -f /etc/squid/squid.conf.candidate
squidmgr ALL=(root) NOPASSWD: /usr/bin/systemctl restart squid
```

That is considerably less than the Docker mode, where the backend needs the
daemon's socket — which is equivalent to root on the machine.

The primary group being `proxy` is not a detail: it is what lets the panel write
the files Squid has to read (the users' htpasswd, the LDAP configuration)
without needing `chown`, which would require privileges. Files holding secrets
are created with mode 640 and group `proxy`, so only root, the panel and Squid
can read them.

### Database

PostgreSQL on the same machine. **SQLite is not an option**: there are nine
operations in the migrations (`drop_column`, `drop_constraint`,
`create_foreign_key`…) that SQLite does not support without
`batch_alter_table`, and the project does not use it.

### Log rotation

The Squid package ships its own `/etc/logrotate.d/squid`; the installer moves it
aside as `squid.dpkg-orig` and puts the project's one in place. The difference
matters: ours forces Squid to reopen the file after rotating it. Without that,
Squid keeps writing to the already-renamed file, `/var/log/squid/access.log`
stops existing, and the panel goes to zero — cards, charts, logs and statistics
all come from there — while browsing keeps working normally, so nothing gives
the failure away.

## Behavioural differences from Docker

There are three, all deliberate.

**The port lives in `squid.conf`.** Under Docker, Squid always listens on a
fixed internal port and Docker publishes the one chosen in the panel. Natively
there is no translation: Squid listens directly wherever the panel says, and
changing the port means rewriting the file and restarting the service, with
nothing to recreate.

**Traffic is measured for the whole machine**, not for a virtual interface
dedicated to the proxy. On a box that acts as a proxy and little else the
difference is negligible; if the machine does other things, its traffic counts
towards the real-time traffic card too.

**Status comes from systemd.** The panel shows `active` / `failed` instead of
`running` / `exited`.

## Operating it

```bash
systemctl status squid squidmanager nginx    # status
journalctl -u squidmanager -f                # panel logs
journalctl -u squid -f                       # Squid logs
```

Configuration lives in `/opt/squid-manager/.env`. After editing it:

```bash
systemctl restart squidmanager
```

## Upgrading

```bash
cd /opt/squid-manager
sudo git pull
sudo backend/.venv/bin/pip install -q -r backend/requirements.txt
cd frontend && sudo npm install --silent && sudo npm run build
sudo systemctl restart squidmanager
```

**The `npm run build` is not optional**, and it is the exact equivalent of
Docker's `--build`: nginx serves the already-compiled files from
`frontend/dist`, so without rebuilding, the panel keeps running the previous
version even though the `git pull` went fine.

The panel applies database migrations when it starts, so there is no separate
step for that.

## Uninstalling

```bash
sudo systemctl disable --now squidmanager squid
sudo rm -f /etc/systemd/system/squidmanager.service /etc/sudoers.d/squidmanager
sudo rm -f /etc/nginx/sites-enabled/squidmanager
sudo systemctl daemon-reload && sudo systemctl reload nginx
sudo rm -rf /opt/squid-manager
```

The database, `/etc/squid` and the certificates are kept on purpose: delete them
separately if you really want to start from scratch.
