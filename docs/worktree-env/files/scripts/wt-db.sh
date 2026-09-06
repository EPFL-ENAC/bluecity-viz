#!/usr/bin/env bash
# Per-branch database for a worktree, cloned from an idle template.
# Two templates exist:
#   resslab_hub_light    (default) ~20 MB rebuilt from the data repo: every main
#                        CSV, dictionary and README, one measurement file per
#                        series type — enough for almost all feature work, and a
#                        clone costs well under a second, so every worktree gets
#                        its own and migrations stay ON.
#   resslab_hub_template full idle copy of the shared 3.4 GB dev dataset, for
#                        branches that need real data volumes or every curve.
# Commands:
#   wt-db.sh template-light  (re)build resslab_hub_light from the data repo — alembic + uploader, ~30 s
#   wt-db.sh template        (re)build resslab_hub_template from the shared DB — pg_dump | psql, minutes, 3.4 GB
#   wt-db.sh create [full]   clone a template into resslab_hub_<slug>, point this worktree at it, migrations ON
#   wt-db.sh drop            drop this worktree's clone, point it back at the shared DB, migrations OFF
#   wt-db.sh status          which DB this worktree uses, and the clones that exist
# Why a template and not `TEMPLATE postgres` directly: Postgres refuses to clone a
# database that has open connections, and the shared one always has some.
set -euo pipefail
SCRIPTS="$(dirname "$(readlink -f "$0")")"
. "$SCRIPTS/wt-lib.sh"
load_env_worktree
cd "$ROOT"
BRANCH="$(current_branch)"
CLONE="resslab_hub_$(slug "$BRANCH")"

db_exists() { [ "$(psql_db -Atc "select 1 from pg_database where datname='$1'")" = 1 ]; }
container_up() { docker ps --format '{{.Names}}' | grep -qx "$DB_CONTAINER" || die "$DB_CONTAINER is not running (make dev-database)"; }
# Point this worktree at DBNAME with migrations UPGRADE (true/false).
point_at() {
  set_env_var .env.worktree DB_NAME "$1"
  set_env_var secrets/.env POSTGRES_DB "$1"
  set_env_var secrets/.env DATABASE_UPGRADE "$2"
}
restart_backend() {
  local s; s="$(session_name "$BRANCH")"
  tmux has-session -t "=$s" 2>/dev/null || return 0
  tmux send-keys -t "=$s:backend" C-c; sleep 1
  tmux send-keys -t "=$s:backend" 'set -a; . "$(git rev-parse --show-toplevel)/.env.worktree"; set +a; make dev' C-m
  echo "restarted backend window of $s"
}

case "${1:-status}" in
  template)
    container_up
    echo "==> rebuilding $TEMPLATE_DB from $SHARED_DB (copies ~3.4 GB — several minutes)"
    psql_db -c "drop database if exists $TEMPLATE_DB" -c "create database $TEMPLATE_DB"
    docker exec -i "$DB_CONTAINER" sh -c "pg_dump -U postgres $SHARED_DB | psql -q -v ON_ERROR_STOP=1 -U postgres $TEMPLATE_DB" >/dev/null
    echo "template ready: $TEMPLATE_DB ($(psql_db -Atc "select pg_size_pretty(pg_database_size('$TEMPLATE_DB'))"))"
    ;;
  template-light)
    container_up
    [ -d "${RESSLAB_DATA_DIR:-$ROOT/../resslab-hub-data}" ] || die "no data repo at ${RESSLAB_DATA_DIR:-$ROOT/../resslab-hub-data}"
    echo "==> rebuilding $LIGHT_TEMPLATE_DB from the data repo (main CSVs + 1 measurement file per series type)"
    psql_db -c "select pg_terminate_backend(pid) from pg_stat_activity where datname='$LIGHT_TEMPLATE_DB'" \
            -c "drop database if exists $LIGHT_TEMPLATE_DB" \
            -c "create database $LIGHT_TEMPLATE_DB" >/dev/null
    # Exported env beats secrets/.env (dotenv never overrides the environment),
    # so the schema and upload land in the template, not this checkout's DB.
    POSTGRES_DB="$LIGHT_TEMPLATE_DB" make -C backend database-upgrade
    POSTGRES_DB="$LIGHT_TEMPLATE_DB" make -C backend upload-data-light
    echo "light template ready: $LIGHT_TEMPLATE_DB ($(psql_db -Atc "select pg_size_pretty(pg_database_size('$LIGHT_TEMPLATE_DB'))"))"
    ;;
  create)
    container_up
    in_worktree || die "clone a branch DB from a worktree, not the main checkout"
    if [ "${2:-}" = "full" ]; then
      SRC="$TEMPLATE_DB"
      db_exists "$SRC" || die "no $TEMPLATE_DB yet — run 'make db-template' once from the main checkout"
    elif db_exists "$LIGHT_TEMPLATE_DB"; then SRC="$LIGHT_TEMPLATE_DB"
    elif db_exists "$TEMPLATE_DB"; then SRC="$TEMPLATE_DB"
    else die "no template yet — run 'make db-template-light' once (or 'make db-template' for the full copy)"
    fi
    if db_exists "$CLONE"; then echo "$CLONE already exists"
    else psql_db -c "create database $CLONE template $SRC"; echo "created $CLONE from $SRC"; fi
    point_at "$CLONE" true
    restart_backend
    echo "this worktree now uses $CLONE; alembic upgrade runs when its backend starts"
    ;;
  drop)
    container_up
    { [ "$CLONE" != "$SHARED_DB" ] && [ "$CLONE" != "$TEMPLATE_DB" ] && [ "$CLONE" != "$LIGHT_TEMPLATE_DB" ]; } || die "refusing to drop $CLONE"
    if db_exists "$CLONE"; then
      psql_db -c "select pg_terminate_backend(pid) from pg_stat_activity where datname='$CLONE'" -c "drop database $CLONE"
      echo "dropped $CLONE"
    fi
    point_at "$SHARED_DB" false
    restart_backend
    echo "this worktree is back on the shared $SHARED_DB (migrations off)"
    ;;
  status)
    echo "checkout: $ROOT ($BRANCH)"
    echo "database: ${DB_NAME:-$SHARED_DB}"
    echo "clones:"
    psql_db -Atc "select datname || '  ' || pg_size_pretty(pg_database_size(datname)) from pg_database where datname like 'resslab_hub_%' order by 1" | sed 's/^/  /'
    ;;
  *) die "usage: wt-db.sh template-light|template|create [full]|drop|status" ;;
esac
