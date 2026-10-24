"""Portable local-video/URL entrypoint. No model API keys or private config."""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit

import video_study


def download(url: str, root: Path, cookies_file: str = '') -> Path:
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('请输入不含账号密码的HTTP/HTTPS视频链接。')
    if cookies_file and not Path(cookies_file).expanduser().is_file():
        raise ValueError('cookie文件不存在。')
    root = root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, '-m', 'yt_dlp', '--ignore-config', '--no-playlist',
        '--restrict-filenames', '--format', 'bv*[height<=?1080]+ba/b[height<=?1080]',
        '--merge-output-format', 'mp4', '--retries', '5', '--fragment-retries', '5',
        '--output', str(root / '%(id)s' / '%(id)s.%(ext)s'),
        '--print', 'after_move:filepath', '--no-simulate']
    if cookies_file:
        command += ['--cookies', str(Path(cookies_file).expanduser().resolve())]
    command += ['--', url]
    print('[video-study] downloading one video with yt-dlp', flush=True)
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        # Do not echo URLs, signed download tokens or cookie diagnostics.
        raise RuntimeError(f'yt-dlp下载失败（退出码{result.returncode}）；检查链接、网络和本地cookie文件。')
    paths = [Path(line.strip()).resolve() for line in result.stdout.splitlines() if line.strip()]
    paths = [path for path in paths if path.is_file() and path.is_relative_to(root)]
    if len(paths) != 1:
        raise RuntimeError('没有获得唯一的下载视频文件；请检查下载目录。')
    (paths[0].parent / 'download-report.json').write_text(json.dumps({
        'date': date.today().isoformat(), 'downloader': 'yt-dlp', 'playlist': False,
        'max_height': 1080, 'file': str(paths[0]), 'bytes': paths[0].stat().st_size,
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return paths[0]


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == 'doctor':
        from doctor import main as doctor_main
        return doctor_main()
    parser = argparse.ArgumentParser(description='Download or analyze one video with local Whisper and Codex CLI.',
        epilog='Extra options are forwarded to video_study.py; use --analysis-help for the full list.')
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--video', help='Local video path')
    source.add_argument('--url', help='Single HTTP/HTTPS video URL supported by yt-dlp')
    parser.add_argument('--download-root', default=str(Path.cwd() / 'Video/Downloads'))
    parser.add_argument('--cookies-file', default='')
    if '--analysis-help' in argv:
        video_study.parse_args(['--help'])
        return 0
    args, remaining = parser.parse_known_args(argv)
    # Validate analysis options before any download starts.
    video_study.parse_args(['--video', args.video or 'downloaded-video', *remaining])
    try:
        video = download(args.url, Path(args.download_root), args.cookies_file) if args.url else Path(args.video).expanduser()
    except (ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return video_study.main(['--video', str(video), *remaining])


if __name__ == '__main__':
    raise SystemExit(main())
