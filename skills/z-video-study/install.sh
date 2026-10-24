#!/bin/sh
set -eu
SKILL_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON=${VIDEO_STUDY_PYTHON:-}
if [ -z "$PYTHON" ]; then
    for candidate in python3.12 python3.13 python3.11 python3; do
        if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
            PYTHON=$candidate
            break
        fi
    done
fi
if [ -z "$PYTHON" ] || ! "$PYTHON" -c 'import sys; sys.exit(sys.version_info < (3, 11))'; then
    echo '需要Python 3.11+；可通过 VIDEO_STUDY_PYTHON 指定解释器。' >&2
    exit 2
fi
if [ ! -x "$SKILL_DIR/.venv/bin/python" ]; then
    if command -v uv >/dev/null 2>&1; then
        uv venv --python "$PYTHON" "$SKILL_DIR/.venv"
    else
        "$PYTHON" -m venv "$SKILL_DIR/.venv"
    fi
fi
if command -v uv >/dev/null 2>&1; then
    uv pip install --python "$SKILL_DIR/.venv/bin/python" -r "$SKILL_DIR/requirements.txt"
else
    "$SKILL_DIR/.venv/bin/python" -m pip install -r "$SKILL_DIR/requirements.txt"
fi
echo 'Python依赖安装完成。接着运行 bash run.sh doctor 检查FFmpeg和Codex登录。'
