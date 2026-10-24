"""Check tools and authentication without reading or printing credentials."""
from importlib.metadata import PackageNotFoundError, version
import json
import shutil
import subprocess
import sys


def main() -> int:
    packages = {}
    for name in ('openai-whisper', 'yt-dlp', 'requests'):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = 'MISSING'
    tools = {name: shutil.which(name) for name in ('ffmpeg', 'ffprobe', 'codex')}
    logged_in = False
    if tools['codex']:
        try:
            from codex_backend import child_environment
            result = subprocess.run([tools['codex'], '-c', 'forced_login_method="chatgpt"', 'login', 'status'],
                env=child_environment(), capture_output=True, text=True, timeout=30)
            logged_in = result.returncode == 0 and 'chatgpt' in (result.stdout + result.stderr).lower()
        except (OSError, subprocess.TimeoutExpired):
            pass
    ok = sys.version_info >= (3, 11) and all(tools.values()) and all(v != 'MISSING' for v in packages.values()) and logged_in
    print(json.dumps({'python': sys.version.split()[0], 'packages': packages, 'tools': tools,
        'chatgpt_login': logged_in, 'requires_api_key': False, 'ready': bool(ok)}, ensure_ascii=False, indent=2))
    if not logged_in:
        print('如未登录，请在自己的终端运行 codex login。', file=sys.stderr)
    return 0 if ok else 2


if __name__ == '__main__':
    raise SystemExit(main())
