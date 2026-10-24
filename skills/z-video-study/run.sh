#!/bin/sh
set -eu
SKILL_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON=${VIDEO_STUDY_PYTHON:-"$SKILL_DIR/.venv/bin/python"}
if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "尚未安装依赖。请先运行：bash \"$SKILL_DIR/install.sh\"" >&2
    exit 2
fi
exec "$PYTHON" "$SKILL_DIR/scripts/cli.py" "$@"
