#!/usr/bin/env bash
# Chỉ dùng database tạm; không kết nối/ghi Supabase, không bật service PostgreSQL.
set -euo pipefail
TASK_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TASK_PG_BIN="${WPCS_PG_BIN:-/opt/homebrew/opt/postgresql@17/bin}"
TASK_PG_DIR="$(mktemp -d /tmp/wpcs-pg.XXXXXX)"
cleanup(){ "$TASK_PG_BIN/pg_ctl" -D "$TASK_PG_DIR/db" stop -m immediate >/dev/null 2>&1 || true; }
trap cleanup EXIT
"$TASK_PG_BIN/initdb" -D "$TASK_PG_DIR/db" --auth=trust >/dev/null
"$TASK_PG_BIN/pg_ctl" -D "$TASK_PG_DIR/db" -l "$TASK_PG_DIR/server.log" -o "-k $TASK_PG_DIR -h '' -p 55435" start >/dev/null
TASK_PSQL=("$TASK_PG_BIN/psql" -h "$TASK_PG_DIR" -p 55435 -d postgres -v ON_ERROR_STOP=1 -X)
"${TASK_PSQL[@]}" -f "$TASK_ROOT/tests/sql/fixture.sql" >/dev/null
for migration in "$TASK_ROOT"/supabase/00*.sql; do "${TASK_PSQL[@]}" -f "$migration" >/dev/null; done
"${TASK_PSQL[@]}" -f "$TASK_ROOT/tests/sql/assertions.sql"
