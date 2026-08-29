# Installation Guide — SquidManager

**[Español](installation.md) · English · [Português](installation.pt.md)**

This guide takes you step by step from an empty server to a working
SquidManager.

> **This is the Docker deployment guide.** If you do not want Docker on that
> machine, there is a second mode where everything runs as system services:
> [instalacion-nativa.en.md](instalacion-nativa.en.md). You pick one of the two;
> they do not coexist on the same machine.

> The Spanish version, [installation.md](installation.md), is the source of
> truth. If they disagree, the Spanish one is right.

---

## Prerequisites

### Operating system
- Ubuntu 20.04 / 22.04 / 24.04 (recommended)
- Any Linux with a working Docker

### Minimum hardware
| Resource | Minimum | Recommended |
|---------|--------|-------------|
| CPU | 2 cores | 4 cores |
| RAM | 2 GB | 4 GB |
| Disk | 5 GB free | 10 GB |
| Swap | 2 GB | 4 GB |

> ⚠️ Compiling Squid from source needs at least 2 GB of RAM plus 2 GB of swap.
> With less, the build may fail.

### Required software
- **Docker** 20.10 or newer
- **Docker Compose** v2 or newer
- **Git**

### Installing Docker (if you do not have it)

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Check
docker --version
docker compose version
```

---

## Two ways to install

> **Does the server reach the internet through a proxy?** Neither of the two
> ways below works as-is: three different proxy configurations are needed
> first. See [instalacion-tras-proxy.md](instalacion-tras-proxy.md) (Spanish).

They do the same thing; the difference is who fills in the configuration.

| | With `install.sh` | Manual |
|---|---|---|
| Where it installs | Wherever you cloned it | Wherever you want |
| `DB_PASS` and `SECRET_KEY` | Generated for you | You define them |
| `PROJECT_DIR` | Filled in for you | **You must set it** |

### With the installer

```bash
git clone https://github.com/luislopezsanchez/squid-manager.git
cd squid-manager
sudo ./install.sh
```

The script generates the keys, prepares the `.env` and brings the containers up.

**It installs into the directory where you cloned it.** If you run the script
on its own, outside a clone, it uses `/opt/squid-manager`. To force another
path:

```bash
sudo INSTALL_DIR=/srv/squid ./install.sh
```

If there was already an installation at that path, it upgrades it keeping the
existing configuration. If it finds uncommitted local changes, it makes a copy
next to the project and stops, rather than letting `git pull` overwrite them.

> Do not pipe the script straight into `bash` from the internet: download it,
> read it and run it, which is what the commands above do.

If you used the installer you can skip to
[Step 4](#step-4-wait-for-squid-to-compile). The rest of this guide describes
the manual installation.

---

## Manual installation, step by step

### Step 1: Clone the repository

```bash
git clone https://github.com/luislopezsanchez/squid-manager.git
cd squid-manager
```

You can clone it anywhere. Note the path down: you need it in the next step.

### Step 2: Configure the environment variables

```bash
cp .env.example .env
```

Edit the `.env` file with your values:

```bash
nano .env
```

**`DB_PASS` and `SECRET_KEY` are mandatory** — the `docker-compose.yml` refuses
to start without them. Generate both with:

```bash
openssl rand -hex 16   # for DB_PASS
openssl rand -hex 32   # for SECRET_KEY
```

If you leave `ADMIN_INITIAL_PASSWORD` empty (the default), the backend generates
a random password for the `admin` account the first time it starts. If you would
rather choose it yourself, set it there before the first `docker compose up`.

**`PROJECT_DIR` is the third value you must set**, and the one most often
forgotten because the system starts fine without it:

```bash
pwd    # copy this path
```

```env
PROJECT_DIR=/the/path/pwd/gave/you
```

It ships with `/opt/squid-manager` as an example, which is where `install.sh`
installs. If you cloned somewhere else and do not change it, everything works
normally except for one thing: **changing the proxy port from the panel stops
updating the `.env`**, and the port reverts on the next `docker compose up -d`,
leaving the proxy unreachable without any warning.

The backend uses that path to recreate the Squid container with Docker Compose,
and needs to see it at the same location it has on the server.

### Step 3: Bring the containers up

```bash
docker compose up -d
```

This creates 4 containers:

| Container | Service | Published port | Description |
|-----------|----------|-------------------|-------------|
| squidmgr-db | PostgreSQL 16 | none (internal) | Database |
| squidmgr-backend | FastAPI | none (internal) | REST API |
| squidmgr-proxy | Squid 6.12 | 3128 | Proxy with SSL Bump |
| squidmgr-frontend | React + Nginx | 3000 | Web panel |

> The backend no longer publishes port 8000 to the host: the frontend talks to
> it over Docker's internal network. If you need to reach the API directly (to
> debug, for instance), use `docker exec` or publish the port yourself in a
> development override.

### Step 4: Wait for Squid to compile

**⚠️ Important:** the first time, the Squid container compiles Squid 6.12 from
source with SSL Bump support (OpenSSL). This takes **10-15 minutes** depending
on the hardware.

You can watch the progress:

```bash
docker compose logs -f squid
```

When you see this message, it is ready:
```
Accepting HTTP Socket connections at conn3 local=[::]:3128
listening port: 3128
```

Press `Ctrl+C` to leave the logs (the container keeps running).

### Step 5: Check that everything works

```bash
# Check that all 4 containers are UP
docker compose ps

# Test the backend from inside its own container
# (the port is not published to the host)
docker exec squidmgr-backend python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health').read())"
# Should answer: {"status":"ok"}

# Test the web panel
curl -o /dev/null -w "%{http_code}" http://localhost:3000/
# Should answer: 200
```

### Step 6: Reach the panel

1. Open your browser at **http://SERVER_IP:3000**
2. Look up the generated password for `admin`:
   ```bash
   docker compose logs backend | grep -A3 "Administrador inicial"
   ```
   (If you set `ADMIN_INITIAL_PASSWORD` in the `.env`, use that one.)
3. Log in with `admin` and that password
4. The panel will ask you to **change it** before letting you in — it is
   mandatory on first access
5. You are in.

---

## Freshly installed, the proxy lets nobody through

Same as in native mode, and for the same reason.

The `squid.conf` the container writes on startup **denies everything except
`localhost`**. The backend replaces it with the definitive, authenticated
configuration as soon as it starts; the first time it may take a while, because
the image compiles Squid from source, so it retries in the background.

Until you create the first proxy user, nobody browses. That is the intent: a
brand-new installation must not sit open to the network while its owner has not
even logged into the panel yet.

---

## Post-installation configuration

### Changing the admin password

Always do it **from the panel**: log in → key icon in the sidebar → "Change
password". Changing it this way invalidates any session open in other browsers.

> Do not change it by writing directly into the database, nor with a script that
> only updates `password_hash`: the system also records when the password was
> changed so it can close old sessions, and a manual change that skips that step
> leaves the session protections orphaned.

### Creating a proxy user

From the panel:
1. Go to **"Users"**
2. Click **"New user"**
3. Enter a username and password (at least 8 characters)
4. Click **"Create user"**

### Configuring the proxy on clients

**In the client's browser:**
- Type: HTTP proxy
- Address: SERVER_IP
- Port: 3128
- Username: the one you created
- Password: the one you set

**Or from the command line (Linux):**
```bash
export http_proxy=http://user:password@SERVER_IP:3128
export https_proxy=http://user:password@SERVER_IP:3128
```

---

## Uninstalling

```bash
# Stop and remove the containers
docker compose down

# Remove the volumes (this deletes all data!)
docker compose down -v

# Remove the images
docker rmi squid-manager-backend squid-manager-frontend squid-manager-squid
```

---

## Upgrading

```bash
git pull origin main
docker compose build
docker compose up -d
```

The database schema is managed with Alembic: pending migrations are applied
automatically when the backend starts. If you are upgrading a very old
installation (from before Alembic was adopted), check the backend log after the
`up -d`:

```bash
docker compose logs backend | grep -i alembic
```
