#!/bin/bash
set -euo pipefail

root=$(cd -- "$(dirname -- "$0")" && pwd -P)
backend="$root/backend"
frontend="$root/frontend"
runtime="$root/.local"
python="$backend/.venv/bin/python"
pg_data="$runtime/preview-pg"
password_file="$runtime/preview-db-password"
database=avito_buddy_demo
db_port=55441
api_port=5050
web_port=5177
origin="http://localhost:$web_port"

fail() {
    printf '%s\n' "$*" >&2
    exit 1
}

preview_ready() {
    local health page
    health=$(curl -fsS --max-time 2 "$origin/health" 2>/dev/null) || return 1
    [[ $health =~ \"status\"[[:space:]]*:[[:space:]]*\"ok\" ]] || return 1
    page=$(curl -fsS --max-time 2 "$origin/" 2>/dev/null) || return 1
    [[ $page =~ \<title\>[^\<]*AI-buddy[^\<]*\</title\> ]]
}

open_preview() {
    open "$origin" || printf 'Open %s in your browser.\n' "$origin"
}

if preview_ready; then
    printf 'AI Buddy is already running at %s.\n' "$origin"
    open_preview
    exit 0
fi

# Finder does not load the PATH from your interactive shell.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if command -v brew >/dev/null; then
    brew_prefix=$(brew --prefix)
    export PATH="$brew_prefix/opt/node@24/bin:$brew_prefix/opt/postgresql@16/bin:$PATH"
fi

command -v python3.12 >/dev/null || fail 'Install Python 3.12.'
if ! command -v node >/dev/null || ! command -v npm >/dev/null; then
    fail 'Install Node.js 20 or later with npm.'
fi
node -e 'process.exit(Number(process.versions.node.split(".")[0]) < 20 ? 1 : 0)' || fail 'Install Node.js 20 or later.'
pg_bin=${POSTGRES_BIN:-}
if [[ -z $pg_bin ]]; then
    pg_ctl=$(command -v pg_ctl) || fail 'Install PostgreSQL 16 or set POSTGRES_BIN to its bin directory.'
    pg_bin=$(dirname -- "$pg_ctl")
fi
for program in pg_ctl initdb psql createdb; do
    [[ -x "$pg_bin/$program" ]] || fail "Could not find $program in $pg_bin. Install PostgreSQL 16."
done

mkdir -p "$runtime"
# The shell holds the advisory lock while it prepares and runs this checkout.
exec 9>"$runtime/preview.lock"
python3.12 -c 'import fcntl; fcntl.flock(9, fcntl.LOCK_EX | fcntl.LOCK_NB)' 2>/dev/null ||
    fail 'AI Buddy is starting in another window. Check that window, then try again.'

api_pid=''
web_pid=''
started_database=false

cleanup() {
    local status=$?
    trap - EXIT
    trap '' INT TERM HUP
    if [[ -n $web_pid ]]; then kill "$web_pid" 2>/dev/null || true; fi
    if [[ -n $api_pid ]]; then kill "$api_pid" 2>/dev/null || true; fi
    if [[ -n $web_pid ]]; then wait "$web_pid" 2>/dev/null || true; fi
    if [[ -n $api_pid ]]; then wait "$api_pid" 2>/dev/null || true; fi
    if $started_database; then
        "$pg_bin/pg_ctl" stop -D "$pg_data" -m fast -w >/dev/null || true
    fi
    if (( status != 0 && status != 129 && status != 130 && status != 143 )); then
        printf 'Preview logs: %s\n' "$runtime" >&2
    fi
    exit "$status"
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

assert_free_port() {
    python3.12 - "$1" <<'PY'
import socket
import sys

port = int(sys.argv[1])
with socket.socket() as listener:
    listener.settimeout(1)
    if listener.connect_ex(("127.0.0.1", port)) == 0:
        sys.exit(f"Port {port} is already in use. Close the other process and try again.")
PY
}

assert_free_port "$api_port"
assert_free_port "$web_port"

if [[ ! -x $python ]]; then
    python3.12 -m venv "$backend/.venv"
fi
"$python" -c 'import sys; sys.exit(sys.version_info[:2] != (3, 12))' ||
    fail 'Use a Python 3.12 virtual environment at backend/.venv.'

(
    cd "$backend"
    checksum=$(shasum -a 256 server/requirements.txt ai/pyproject.toml)
    stamp=.venv/avito-start-dependencies
    if [[ ! -f $stamp || $(<"$stamp") != "$checksum" ]]; then
        "$python" -m pip install -r server/requirements.txt -e ./ai
        printf '%s\n' "$checksum" > "$stamp"
    fi
)
(
    cd "$frontend"
    checksum=$(shasum -a 256 package-lock.json)
    stamp=node_modules/.avito-start-dependencies
    if [[ ! -f node_modules/vite/bin/vite.js || ! -f $stamp || $(<"$stamp") != "$checksum" ]]; then
        npm ci
        printf '%s\n' "$checksum" > "$stamp"
    fi
)

if [[ ! -f "$pg_data/PG_VERSION" ]]; then
    assert_free_port "$db_port"
    if [[ ! -f $password_file ]]; then
        (umask 077; "$python" -c 'import secrets; print(secrets.token_hex(24))' > "$password_file")
    fi
    "$pg_bin/initdb" -D "$pg_data" -U buddy --auth=scram-sha-256 --encoding=UTF8 --locale=C "--pwfile=$password_file"
fi
[[ -s $password_file ]] || fail "Missing database password at $password_file."
PGPASSWORD=$(<"$password_file")
export PGPASSWORD
export DATABASE_URL="postgresql://buddy@127.0.0.1:$db_port/$database"

if ! "$pg_bin/pg_ctl" status -D "$pg_data" >/dev/null; then
    assert_free_port "$db_port"
    "$pg_bin/pg_ctl" start -D "$pg_data" -l "$runtime/preview-postgres.log" \
        -o "-h 127.0.0.1 -p $db_port -c unix_socket_directories=" -w 9>&-
    started_database=true
fi
db_args=(-w -h 127.0.0.1 -p "$db_port" -U buddy)
existing_db=$("$pg_bin/psql" "${db_args[@]}" -d postgres -Atc "SELECT datname FROM pg_database WHERE datname = '$database'")
if [[ -z $existing_db ]]; then
    "$pg_bin/createdb" "${db_args[@]}" "$database"
fi

export PUBLIC_ORIGIN="$origin" PORTAL_PROTECT_LEGACY=1 SESSION_COOKIE_SECURE=0
export AI_MODE=demo BUDDY_AGENT_FACTORY='' PYTHONPATH="$backend/ai"
(
    cd "$backend"
    "$python" -m server.store migrate
    "$python" -m server.store seed
)
(
    cd "$backend"
    exec "$python" -m waitress "--listen=127.0.0.1:$api_port" --call server.app:create_app
) > "$runtime/preview-api.log" 2>&1 9>&- &
api_pid=$!

(
    cd "$frontend"
    export VITE_ENABLE_MSW=false VITE_API_URL=''
    exec node node_modules/vite/bin/vite.js --config vite.integrated.config.ts --host 127.0.0.1 --port "$web_port" --strictPort
) > "$runtime/preview-web.log" 2>&1 9>&- &
web_pid=$!

for ((attempt=0; attempt<40; attempt++)); do
    kill -0 "$api_pid" "$web_pid" 2>/dev/null || fail 'A preview process stopped during startup.'
    if preview_ready; then
        printf 'AI Buddy is ready at %s. Press Ctrl+C to stop.\n' "$origin"
        open_preview
        while kill -0 "$api_pid" "$web_pid" 2>/dev/null; do sleep 1; done
        fail 'A preview process stopped.'
    fi
    sleep 0.5
done
fail "The preview did not become available at $origin."
