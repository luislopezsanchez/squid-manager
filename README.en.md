# SquidManager

**[Español](README.md) · English · [Português](README.pt.md)**

<p align="center">
  <strong>Web management panel for Squid Proxy, with FastAPI, React and SSL Bump</strong><br>
  Deploys <strong>with Docker</strong> or <strong>without Docker</strong>
</p>

<p align="center">
  <img alt="License" src="https://img.shields.io/badge/license-Apache--2.0-blue.svg">
  <img alt="Squid" src="https://img.shields.io/badge/Squid-6.12%20%7C%206.14-green">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.115-teal">
  <img alt="React" src="https://img.shields.io/badge/React-18-blue">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-16-blue">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-Compose-blue">
</p>

> **The Spanish version is the source of truth.** If this translation and
> [README.md](README.md) ever disagree, the Spanish one is right.

> ### 🌍 Documentation languages
>
> | | Español | English | Português |
> |---|---|---|---|
> | **README** | [README.md](README.md) | this one | [README.pt.md](README.pt.md) |
> | **Install with Docker** | [ver](docs/installation.md) | [view](docs/installation.en.md) | [ver](docs/installation.pt.md) |
> | **Install without Docker** | [ver](docs/instalacion-nativa.md) | [view](docs/instalacion-nativa.en.md) | [ver](docs/instalacion-nativa.pt.md) |
>
> The rest of the documentation is Spanish only. The **panel and the API
> messages** do speak all three languages: pick one in the top-bar selector —
> see [docs/idiomas.md](docs/idiomas.md).

---

## 📋 Table of contents

- [Overview](#-overview)
- [Features](#-features)
- [Architecture](#-architecture)
- [Requirements](#-requirements)
- [Installation](#-installation)
  - [Mode A — with Docker](#mode-a--with-docker)
  - [Mode B — without Docker (native)](#mode-b--without-docker-native-installation)
- [Upgrading](#-upgrading)
- [Configuration](#-configuration)
- [Getting started](#-getting-started)
- [SSL Bump (HTTPS)](#-ssl-bump-https)
- [Web panel](#-web-panel)
- [REST API](#-rest-api)
- [Documentation](#-documentation)
- [Troubleshooting](#-troubleshooting)
- [License](#-license)

---

## 📖 Overview

**SquidManager** is a complete Squid Proxy management platform. It lets network
administrators configure and run a Squid proxy from a friendly web interface,
without editing configuration files by hand.

The system is designed to be **scalable and modular**: the database is the
source of truth, `squid.conf` is generated dynamically from the web panel, and
everything runs either in Docker containers or as system services.

---

## ✨ Features

### Proxy management
- **Visual ACLs** — Build access control lists by domain, IP, schedule, regex, port, HTTP method and more (27 supported types)
- **Access rules** — Order `http_access` rules with move up/down buttons
- **User groups** — Group local or LDAP users and apply access policies to the whole group at once
- **Delay Pools** — Per-user bandwidth control with a visual interface (no need to understand the `64000/64000 64000/32000` format)
- **General settings** — Port, cache, logging, realm, visible hostname: all editable from the web

### Authentication
- **Local users** — Full user management with basic authentication (htpasswd) and an optional expiry date
- **LDAP / Active Directory** — Integration with an external directory, with a built-in connection test and paginated synchronisation
- **Secure panel** — JWT login, roles (superadmin / admin / read-only) and a mandatory password change on first access

### Security
- **SSL Bump** — Intercepts and filters HTTPS traffic, not just HTTP
- **HTTPS blocking by SNI** — Blocks domains before decrypting (e.g. Facebook or YouTube over HTTPS)
- **Sensitive domain exclusion** — Banking, healthcare or apps using *certificate pinning* can be left out of decryption
- **Full audit trail** — A log of every change: who, what, when
- **CA certificate** — Generated automatically and downloadable from the panel, with installers for Windows, macOS and iOS

### Operations
- **Apply changes live** — Validates the configuration against Squid *before* writing it; reloads or restarts as needed
- **Automatic port change** — Detects a port change and recreates the container without losing the configuration if something fails
- **Dashboard** — Real-time traffic, top users and domains, system status
- **Backup and migration** — Export the whole configuration to JSON (groups and LDAP users included) or import a traditional `squid.conf`
- **Notifications** — Email or Telegram alerts when changes are applied or suspicious activity is detected

### Deployment and languages
- **Two deployment modes** — With Docker (a single command brings everything up) or **without Docker**, with Squid, the panel and PostgreSQL running as system services. Chosen with `DEPLOY_MODE`; the rest of the product is identical — see [docs/instalacion-nativa.en.md](docs/instalacion-nativa.en.md)
- **No root** — In native mode the panel runs under its own user with a three-command sudoers file, considerably less than what the Docker socket grants
- **Panel in three languages** — Spanish, English and Portuguese, selectable from the panel itself. API error messages are translated too, and the error pages your proxy users see follow their own language — see [docs/idiomas.md](docs/idiomas.md)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Network                        │
│                                                          │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐        │
│  │ Frontend  │     │ Backend  │     │ Squid    │        │
│  │ (React)  │────▶│ (FastAPI)│────▶│ Proxy    │        │
│  │ :3000    │     │ :8000    │     │ :3128    │        │
│  └──────────┘     └────┬─────┘     └──────────┘        │
│                        │                                 │
│                   ┌────▼─────┐                          │
│                   │PostgreSQL│                          │
│                   │  :5432   │                          │
│                   └──────────┘                          │
└─────────────────────────────────────────────────────────┘

Configuration flow:
  Admin → Web panel → REST API → PostgreSQL → Jinja2 → squid.conf → Squid
```

**Key principle:** the database is the source of truth. `squid.conf` is
generated dynamically with Jinja2 from the data in PostgreSQL. When you press
"Apply changes", the backend generates the file, **validates it by running
`squid -k parse` where Squid actually lives**, and only writes and reloads it if
it is valid.

> The backend's port 8000 is internal: the frontend talks to the API over the
> Docker network, and it is not published to the host.

More detail in [docs/architecture.md](docs/architecture.md).

---

## ✅ Requirements

Requirements depend on the deployment mode.

### With Docker

- **System:** Linux (Ubuntu 24.04 recommended), or anything with Docker
- **Docker** 20.10+ ([install](https://docs.docker.com/engine/install/))
- **Docker Compose** v2+ ([install](https://docs.docker.com/compose/install/))
- **Git** (to clone the repository)

### Without Docker (native installation)

- **System:** Ubuntu 22.04 / 24.04 or Debian 12, x86_64 — **not** any Linux,
  because the `squid-openssl` package is required
- **Root access** and internet access to download packages
- Nothing else: the installer sets up Squid, PostgreSQL, nginx, Node and Python

### Minimum hardware
- **CPU:** 2 cores (4 recommended; with Docker, Squid is compiled while building the image)
- **RAM:** 2 GB (4 GB recommended)
- **Disk:** 5 GB free
- **Network:** port 3128 reachable by the proxy clients

---

## 🚀 Installation

**Start by choosing a deployment mode.** There are two, and they are mutually
exclusive: on a given machine you use one **or** the other, never both.

| | **Mode A — with Docker** | **Mode B — without Docker (native)** |
|---|---|---|
| What it brings up | 4 containers | System services, under systemd |
| What it requires | Docker 20.10+ and Compose v2+ | Ubuntu 22.04 / 24.04 or Debian 12, x86_64 |
| Squid | Compiled while building the image | `squid-openssl` package; **compiles nothing** |
| How long it takes | 15-30 min the first time, because it compiles Squid | 3-5 min |
| What privileges the panel gets | The Docker socket, which is equivalent to root on the machine | Its own user and three `sudo` commands |
| Do you clone the repo | Yes | No: downloading one script is enough |
| Choose it if | You want container isolation and Docker is not a problem | Internal policy does not allow Docker, or the machine already acts as a proxy and one more layer is one too many |

The two full step-by-step guides are
[docs/installation.en.md](docs/installation.en.md) (Docker) and
[docs/instalacion-nativa.en.md](docs/instalacion-nativa.en.md) (native).

---

### Mode A — with Docker

There are two paths. They do the same thing; the difference is who fills in the
configuration.

| | A1: with `install.sh` | A2: manual |
|---|---|---|
| Where it installs | Wherever you cloned it | Wherever you want |
| `DB_PASS` and `SECRET_KEY` | Generated for you | You define them |
| `PROJECT_DIR` | Filled in for you | **You must set it** |

#### A1 — with the installer

Generates the keys, prepares the `.env` and brings the containers up.

```bash
git clone https://github.com/luislopezsanchez/squid-manager.git
cd squid-manager
sudo ./install.sh
```

**It installs into the directory where you cloned it**, not into a fixed path.
If you run the script on its own, outside a clone, it uses
`/opt/squid-manager`. You can also force the path:

```bash
sudo INSTALL_DIR=/srv/squid ./install.sh
```

If there was already an installation at that path, it upgrades it while keeping
the configuration; if you have uncommitted local changes, it makes a copy and
stops rather than overwriting them.

> Do not pipe the script straight into `bash` from the internet: download it,
> read it and run it, which is what the commands above do.

##### If the server reaches the internet through a proxy

`install.sh` assumes direct internet access. When the network forces everything
through a corporate proxy, **three** separate layers need configuring — the
host, the Docker daemon and the builds — and configuring only one leaves the
installation half done, usually with a `Could not resolve` in the middle of an
`apt-get`. A second script handles that:

```bash
cp proxy.conf.example proxy.conf
```

Put your details in `proxy.conf` (server, port and, if needed, username and
password; special characters do not need escaping) and run:

```bash
sudo ./install-tras-proxy.sh
```

It configures the three layers, checks that each one reaches the internet, and
only then runs `install.sh`. The credentials live in `proxy.conf`, which is in
`.gitignore`: no repository file is edited, because an uncommitted local change
would make the installer abort.

This is only for **installing**. To make Squid reach the internet through the
corporate proxy once installed, configure it from the panel under **Parent
proxy** — see [docs/proxy-padre.md](docs/proxy-padre.md).

The equivalent manual procedure, what each step touches, and what to do if the
proxy inspects TLS, is in
[docs/instalacion-tras-proxy.md](docs/instalacion-tras-proxy.md).

#### A2 — manual

Choose this if you want the project somewhere else or prefer to control each
step.

```bash
# 1. Clone the repository (wherever you prefer)
git clone https://github.com/luislopezsanchez/squid-manager.git
cd squid-manager

# 2. Copy the example configuration
cp .env.example .env

# 3. Edit the .env (see below what is mandatory)
nano .env

# 4. Bring the whole system up
docker compose up -d

# 5. Wait for Squid to compile (first time: ~10-15 minutes)
#    Watch the progress:
docker compose logs -f squid

# 6. When you see "Accepting HTTP Socket connections", it is ready
```

**Three values in the `.env` must be set, no exceptions:**

```env
DB_PASS=            # mandatory: openssl rand -hex 16
SECRET_KEY=         # mandatory: openssl rand -hex 32
PROJECT_DIR=        # the ABSOLUTE path where you just cloned the project
```

> **`PROJECT_DIR` is the one people forget.** It ships with
> `/opt/squid-manager` as an example. If you cloned somewhere else and do not
> change it, the system starts and works normally, but **changing the proxy
> port from the panel stops updating the `.env`**, and the port reverts on the
> next `docker compose up -d`. Check with `pwd` and use that exact path.
> (With A1 you do not need to worry: the installer fills it in.)

#### Access and first login (Docker)

| Service | URL |
|----------|-----|
| **Web panel** | http://SERVER_IP:3000 |
| **Squid proxy** | SERVER_IP:3128 |

There is no default password. The `admin` user is created with a **random
password** that appears **only once** in the backend log:

```bash
docker compose logs backend | grep -A3 "Administrador inicial"
```

You will be asked to change it before you can use the panel. If you would
rather set it yourself, define `ADMIN_INITIAL_PASSWORD` in the `.env` before the
first start.

> The backend API (port 8000) is not published to the host: the panel talks to
> it over Docker's internal network. The interactive documentation (`/docs`) is
> only available if you start with `DEBUG=true` in the `.env`.

---

### Mode B — without Docker (native installation)

Squid, the panel, PostgreSQL and nginx running as system services. **You do not
clone the repository, you do not edit any `.env`, and nothing gets compiled**:
the installer takes care of everything.

On a freshly installed Ubuntu 22.04 / 24.04 or Debian 12, with root access:

```bash
# 1. Download the installer
wget https://raw.githubusercontent.com/luislopezsanchez/squid-manager/main/install-nativo.sh

# 2. Read it before running it as root (always, wherever it came from)
less install-nativo.sh

# 3. Make it executable
chmod +x install-nativo.sh

# 4. Run it
sudo ./install-nativo.sh
```

It takes three to five minutes. When it finishes it prints the panel URL, the
username and the initial password.

**If you want different ports**, pass them as environment variables (note the
`-E`, which is what makes `sudo` keep them):

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

#### What the installer does, in order

1. Checks that the system is supported.
2. Installs the packages: `squid-openssl`, PostgreSQL, nginx, Node, Python and
   `apache2-utils`. **`squid-openssl`, not `squid`**: the plain package is the
   GnuTLS flavour, with no SSL bump and no certificate generator.
3. Creates the `squidmgr` user, with `proxy` as its primary group.
4. Clones the code into `/opt/squid-manager`.
5. Creates the PostgreSQL database.
6. Generates the CA for SSL Bump and installs the authentication helper.
7. Writes a sudoers file with **three literal commands**, no wildcards.
8. Prepares the Python environment, the `.env` and the systemd unit.
9. Builds the web panel and configures nginx.
10. Starts the services and checks that they respond.

#### Access and first login (native)

The installer finishes by printing exactly this:

```
  Panel:    http://SERVER_IP:3000
  Proxy:    SERVER_IP:3128
  Usuario:  admin
  Clave:    <randomly generated password>
```

That password **is not shown again**, and the panel will ask you to change it on
first access. If you lose it before logging in, it is in the log:

```bash
journalctl -u squidmanager | grep -A3 "Administrador inicial"
```

To operate the service afterwards:

```bash
systemctl status squid squidmanager nginx    # status
journalctl -u squidmanager -f                # panel logs
```

The behavioural differences from Docker — where the port lives, how traffic is
measured, what status the panel shows — are in
[docs/instalacion-nativa.en.md](docs/instalacion-nativa.en.md).

---

### After installing, in either mode

**1. Open the proxy port in the server firewall.** Neither the installer nor
the panel does it:

```bash
sudo ufw allow 3128/tcp
```

Without that rule Squid works but clients cannot reach it, and the symptom is a
connection that hangs with no error message at all.

**2. Create the first proxy user**, under *Users → New user*. Until then nobody
browses: the proxy requires credentials from minute one and there are none yet.
That is on purpose, and it is explained above in
[Getting started](#-getting-started).

---

## 🔄 Upgrading

```bash
cd /path/to/squid-manager && git pull && docker compose up -d --build
```

Database migrations are applied automatically when the backend starts, and
**your configuration is preserved**: users, rules, ports and certificates are
left alone.

> **The `--build` is not optional.** Without it, Docker reuses the images it
> already has and the new code never runs, even though the `git pull` went
> fine. Everything looks right — repository up to date, containers started —
> but you are still on the previous version.

In a native installation the equivalent step is `npm run build`, for exactly the
same reason: nginx serves already-compiled files.

To check it went well:

```bash
cd /path/to/squid-manager && git log --oneline -1 && git status --porcelain | wc -l && docker compose ps
```

You should see the expected commit, **0** pending files, and the four
containers `healthy`.

See [docs/actualizacion.md](docs/actualizacion.md) to verify the database
revision, resolve a `git pull` that aborts, a migration that fails, or to roll
back to a previous version.

---

## 🔧 Configuration

Everything is configured through the `.env` file:

```env
# PostgreSQL
DB_NAME=squidmanager
DB_USER=squid
DB_PASS=                    # MANDATORY: openssl rand -hex 16

# Panel security
SECRET_KEY=                 # MANDATORY: openssl rand -hex 32
TOKEN_EXPIRE=480
ADMIN_INITIAL_PASSWORD=     # empty = random, shown once in the log
BCRYPT_COST=12

# Network and CORS
CORS_ORIGINS=                     # empty if the panel is served from its own URL
TRUSTED_PROXY_HOSTS=frontend      # hosts whose X-Forwarded-For is accepted
DEBUG=false                       # true exposes /docs without authentication

# Deployment
DEPLOY_MODE=docker                # docker (container) or native (systemd)
NATIVE_SQUID_SERVICE=squid        # systemd unit name, native mode only

# Paths
PROJECT_DIR=/opt/squid-manager    # ABSOLUTE path of this directory; install.sh fills it in

# Ports
WEB_PORT=3000
PROXY_PORT=3128                   # proxy port; the panel updates it when you change it
```

> `PROJECT_DIR` must point at where the project lives: the backend uses it to
> recreate the Squid container with Compose when the port changes. `install.sh`
> writes it for you; if you install by hand or move the project, adjust it.

For every option, see [docs/configuration.md](docs/configuration.md).

---

## 📚 Getting started

After installing:

> **Freshly installed, the proxy lets nobody through, and that is on purpose.**
> Squid starts up denying everything except `localhost`; the panel replaces that
> right away with the definitive configuration, which requires a username and
> password. Until you create the first proxy user, nobody browses. This holds
> for both deployment modes: a brand-new installation must not sit open to the
> network while its owner has not even logged into the panel.

1. **Open the panel** → http://localhost:3000
2. **Log in** with `admin` and the generated password (see above)
3. **Change the password** when the panel asks you to
4. **Create a proxy user** → "Users" page → "New user"
5. **Configure your browser** with the proxy:
   - IP: `localhost` (or the server's IP)
   - Port: `3128`
   - Username: the one you created
   - Password: the one you set
6. **Browse** → your traffic now goes through Squid
7. **Create an ACL** → "ACLs" page → "New ACL" (e.g. block `.facebook.com`)
8. **Create a rule** → "Access rules" page → "New rule" → `deny` + your ACL
9. **Apply changes** → "Apply changes" button in the sidebar
10. **Test it** → try browsing to Facebook → it should be blocked

---

## 🔐 SSL Bump (HTTPS)

SquidManager includes **SSL Bump**, which allows intercepting and filtering
HTTPS traffic.

### How it works
1. Squid generates a **root CA** automatically on first start
2. For each HTTPS connection, Squid generates a dynamic certificate signed by that CA
3. Squid decrypts the traffic, applies the rules (ACLs, delay pools), and re-encrypts it
4. The client's browser must trust Squid's CA

Domains that must not be intercepted (banking, healthcare, apps with
*certificate pinning*) can be excluded from decryption under **Settings →
Security → excluded domains**.

### Enabling it on clients
1. Open the panel → **"Certificate"**
2. Download `squidmanager-ca.crt` (or the installer for your system)
3. Install it in the system/browser **"Trusted Root Certification Authorities"** store
4. Restart the browser

For per-operating-system instructions, see [docs/ssl-bump.md](docs/ssl-bump.md).

---

## 🖥️ Web panel

The panel is organised into three groups:

| Group | Section | Purpose |
|-------|---------|---------|
| **Monitoring** | Dashboard | Proxy status, real-time traffic, top users and domains |
| | Logs | access.log viewer, with filters and brute-force alerts |
| | Audit | Log of every change made |
| **Policies** | Users | Proxy user management |
| | Groups | Group users and apply policies to the whole group |
| | ACLs | Access control list management |
| | Access rules | `http_access` rule management with reordering |
| | Bandwidth | Delay pool management (speed limiting) |
| **System** | LDAP | LDAP / Active Directory configuration |
| | Certificate | CA download plus per-OS installers |
| | Settings | General Squid parameters |
| | Notifications | Email and Telegram alerts |
| | Backup and migration | Export/restore configuration, import a squid.conf |
| | Administrators | Panel account management (superadmin only) |

---

## 🔌 REST API

**The interactive documentation is not reachable from outside the server.** Port
8000 is not published to the host, so `http://YOUR_SERVER:8000/docs` never
answers — and on a machine running other services you could end up looking at
another container's API. It is also only registered with `DEBUG=true`; with the
default it returns 404.

If you need to consult it:

```bash
# 1. DEBUG=true in the .env, then recreate the backend
docker compose up -d --force-recreate backend
```

```bash
# 2. From the server itself, against the container's IP
curl http://$(docker inspect squidmgr-backend --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'):8000/openapi.json
```

Opening the Swagger interface in your browser requires an SSH tunnel to that
container IP, which the server can reach but your machine cannot.

> Set `DEBUG=false` again when you are done: that route is served without
> authentication.

The panel uses the API through nginx, under `/api/`, and that path *is*
published — it answers on the panel's port.

### Response language

Error messages come back in **Spanish, English or Portuguese** depending on the
request's `Accept-Language` header. Without a header, or with an unsupported
language, it answers in Spanish. See [docs/idiomas.md](docs/idiomas.md).

### Main endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | Admin login (JWT) |
| GET | `/api/proxy-users/` | List proxy users |
| POST | `/api/proxy-users/` | Create a user |
| GET | `/api/groups/` | List user groups |
| GET | `/api/acls/` | List ACLs |
| POST | `/api/acls/` | Create an ACL |
| GET | `/api/access-rules/` | List rules |
| PUT | `/api/access-rules/reorder` | Reorder rules |
| GET | `/api/delay-pools/` | List delay pools |
| GET | `/api/squid/settings` | Read the configuration |
| POST | `/api/squid/apply` | Validate and apply changes to Squid |
| GET | `/api/squid/status` | Squid status |
| GET | `/api/squid/ca-cert` | Download the CA certificate |
| GET | `/api/ldap/config` | Read the LDAP configuration |
| POST | `/api/ldap/test` | Test the LDAP connection |
| GET | `/api/backup/export` | Export the whole configuration to JSON |
| GET | `/api/panel/dashboard` | Dashboard metrics |
| GET | `/api/logs/access` | Query the access.log |
| GET | `/api/audit/` | List the audit log |

> Metrics are served under **both** `/api/metrics/*` and `/api/panel/*` — the
> same endpoints. Use `/api/panel` from a browser: ad blockers and privacy
> filters cut any URL containing "metrics" because they associate it with
> telemetry, and the request never even leaves the browser.

14 routers and 72 endpoints in total. For the complete documentation, see
[docs/api-reference.md](docs/api-reference.md).

---

## 📚 Documentation

The full documentation is in Spanish. Translated into English:

- [Installation guide](docs/installation.en.md)
- [Native installation, without Docker](docs/instalacion-nativa.en.md)

In Spanish:

| Document | Description |
|-----------|-------------|
| [docs/idiomas.md](docs/idiomas.md) | Panel, API and proxy languages |
| [docs/configuration.md](docs/configuration.md) | Every configuration option |
| [docs/architecture.md](docs/architecture.md) | Detailed technical architecture |
| [docs/authentication.md](docs/authentication.md) | Accounts, sessions, roles and groups |
| [docs/ssl-bump.md](docs/ssl-bump.md) | SSL Bump guide and CA certificates |
| [docs/proxy-padre.md](docs/proxy-padre.md) | Reaching the internet through another proxy |
| [docs/instalacion-tras-proxy.md](docs/instalacion-tras-proxy.md) | Installing on a server behind a proxy |
| [docs/actualizacion.md](docs/actualizacion.md) | How to upgrade, verify and roll back |
| [docs/backup-restore.md](docs/backup-restore.md) | Backup, restore and migration |
| [docs/production.md](docs/production.md) | Production deployment |
| [docs/api-reference.md](docs/api-reference.md) | Complete API documentation |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute |

---

## 🛠️ Troubleshooting

### The Squid container will not start
```bash
docker compose logs squid
```
The first time, Squid is compiled from source (~10-15 minutes). Wait for
"Accepting HTTP Socket connections".

### The proxy does not block HTTPS sites
You need SSL Bump. See [docs/ssl-bump.md](docs/ssl-bump.md).

### The browser shows a certificate warning
Install the CA certificate from the panel → "Certificate".

### I cannot reach the panel
```bash
docker compose ps              # check every container is UP
docker compose logs backend    # look for backend errors
```

### The dashboard stays on "Loading metrics…"

Almost always an ad blocker. The panel asks for `/api/panel/dashboard` precisely
to avoid this, but an aggressive custom filter can still cut it. Check the
browser console for `ERR_BLOCKED_BY_CLIENT`, and if that is it, allow the
panel's address in your blocker.

### I reinstalled and the backend will not start: "password authentication failed"

The data volume from the previous installation survived. The password of an
existing database **is not changed by putting a new one in the `.env`**:
`POSTGRES_PASSWORD` only takes effect the first time, when PostgreSQL creates
the empty database. If the volume already existed, it keeps the original
password and the backend, using the new one, cannot get in.

Watch out when reinstalling under another path: Compose names volumes after the
project's **directory name**, so two installations in different paths but with
the same folder name (`squid-manager`) share a volume.

```bash
# See whether a previous installation's volume exists
docker volume ls | grep pgdata
```

Two ways out:

```bash
# 1) Start over. THIS DELETES ALL DATA (users, rules, history)
docker compose down -v && docker compose up -d
```

```bash
# 2) Keep the data: recover the DB_PASS the database was created with,
#    put it in the .env and bring it up again
docker compose up -d
```

The installer checks for this before generating a new `.env` and stops if it
finds an orphan volume, instead of leaving the system half configured.

### I do not remember the initial admin password
Change it from a database session, or check whether it is still in the log:
```bash
docker compose logs backend | grep -A3 "Administrador inicial"
```

### Reaching the internet through another proxy (parent and child)

In many companies the firewall closes direct egress and all traffic has to go
through the corporate proxy. SquidManager can sit behind another proxy, and it
is configured under **Panel → Parent proxy**.

The split of responsibilities is what makes it work:

| | Child (the lower one) | Parent (the upper one) |
|---|---|---|
| Authenticates users | **Yes** | No: it trusts the child |
| Filters by domain | **Yes** | No |
| Intercepts HTTPS | **Yes** | **No**: it only tunnels |
| Reaches the internet | No: through the parent | **Yes** |

Chaining two proxies needs four settings, and missing any one of them breaks it:

1. **On the child**: the parent's server, port and — if required — credentials
2. **On the child**: the parent's CA certificate, if the parent also intercepts HTTPS
3. **On the parent**: `trusted_sources` with the child's IP, so it is not asked for credentials
4. **On the parent**: `ssl_bump_enabled = false`, because only one of them can intercept HTTPS

If both are SquidManager, they also need a different `visible_hostname`: Squid
rejects as a loop anything already carrying its own name in the `Via` header.

To check that it works, the last column of the child's access log changes from
`HIER_DIRECT` to `FIRSTUP_PARENT`.

> **Full guide in [docs/proxy-padre.md](docs/proxy-padre.md)**: why each piece
> is needed, the step-by-step configuration, and a table to identify which of
> the four settings is missing from the symptom — they all produce errors that
> never mention the cause.

### Exempting a group from HTTPS interception

Under **Groups**, each group has a **"Do not intercept this group's HTTPS"**
checkbox. Its members browse with end-to-end encrypted traffic.

It covers two common cases:

- **Machines where the certificate cannot be installed**: personal phones, BYOD, guest devices
- **Tools that break when intercepted**: git, npm, docker and anything using *certificate pinning*

> **Exempting from decryption is not exempting from filtering.** Domain blocking
> acts on the SNI, before decrypting, so it still applies to those users. They
> also still authenticate and are still logged. The only thing lost is
> inspection of the full URL and of the content.

To confirm it is working, their HTTPS connections appear in the access log as
`TCP_TUNNEL/200 CONNECT`, without the decrypted request (`GET https://…`) you
see for everyone else.

### Sources that do not have to authenticate

Under **Settings → Security**, the `trusted_sources` setting accepts IPs or
networks that may browse without credentials:

```
trusted_sources = 203.0.113.10 198.51.100.0/24
```

Intended for a child proxy that already authenticates its own users. Empty by
default: everyone must authenticate.

> This is an authentication exemption: give the specific source. If that IP is a
> shared NAT egress, **every machine behind it is exempt**.

### Using your own DNS servers (a Pi-hole, for example)

Squid resolves names on its own, so you can tell it which servers to ask and
make the proxy's browsing inherit the filtering of a Pi-hole, an AdGuard or your
company's internal DNS.

1. Panel → Settings → `dns_nameservers` → the IPs separated by spaces
2. Press **Test** to check they answer
3. Save → Apply changes

```
dns_nameservers 172.27.0.1
```

Empty = Squid uses the system resolver (the default behaviour).

**IPs only, not hostnames.** Squid has to be able to ask without resolving
anything first, which is exactly what it cannot do yet.

> **With more than one server, filtering is no longer guaranteed.** Squid
> spreads queries across every server in the list, it does not use them as
> fallbacks: adding a public DNS next to the Pi-hole means the share of queries
> that land on the public one resolves unfiltered. For **everything** to go
> through the filter, leave a single server.

When applying, the servers are checked for a real answer and the change is
rejected if they do not respond. That is deliberate: an unreachable DNS does not
break one website, it stops resolving all of them at once, and the symptom does
not point at the cause.

If the Pi-hole runs as a container on the same machine, use the gateway IP of
its Docker network (`docker network inspect`), not `127.0.0.1`: inside Squid's
container that address is Squid itself.

### Changing the proxy port
1. Panel → Settings → `http_port` → set the new port → Save
2. Panel → Apply changes

No file needs editing by hand. In Docker mode the backend updates `PROXY_PORT`
in the `.env` and recreates the container with Docker Compose, so the change
also survives a `docker compose up -d` or a machine reboot. In native mode the
port goes straight into `squid.conf` and the service is restarted.

**Open the new port in the server firewall** and close the old one if it is no
longer used:

```bash
sudo ufw allow 8128/tcp && sudo ufw delete allow 3128/tcp
```

The panel does not manage the firewall. Without that rule Squid listens
correctly but clients never arrive, and the symptom is a connection that hangs
with no error message.

> In Docker mode Squid always listens on **3128 inside the container**; the port
> you choose is the one Docker publishes outwards. That is why `squid.conf`
> shows `http_port 3128` even though clients connect to another port: the port
> lives in a single place (`PROXY_PORT`) and so cannot drift out of sync.

---

## 📝 License

Apache-2.0 — see [LICENSE](LICENSE) for details.

---

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) to learn how to contribute to the
project.
