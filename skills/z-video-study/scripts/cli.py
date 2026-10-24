"""Portable local-video/URL entrypoint. No model API keys or private config."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit

import video_study


def download(url: str, root: Path, cookies_file: str = '', title: str = '') -> Path:
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('请输入不含账号密码的HTTP/HTTPS视频链接。')
    if cookies_file and not Path(cookies_file).expanduser().is_file():
        raise ValueError('cookie文件不存在。')
    root = root.expanduser().resolve()
    command = [sys.executable, str(Path(__file__).with_name('download_video.py')),
        '--out-root', str(root)]
    if cookies_file:
        command += ['--cookies-file', str(Path(cookies_file).expanduser().resolve())]
    if title:
        command += ['--title', title]
    command += ['--', url]
    env = dict(os.environ)
    env['PATH'] = str(Path(sys.executable).parent) + os.pathsep + env.get('PATH', '')
    print('[video-study] downloading through the original z-video-downloader implementation', flush=True)
    result = subprocess.run(command, capture_output=True, text=True, env=env)
    if result.returncode:
        # Do not echo URLs, signed download tokens or cookie diagnostics.
        raise RuntimeError(f'视频下载失败（退出码{result.returncode}）；检查下载目录中的download-report.md，或用 run.sh download 单独重试。')
    reports = [Path(line.strip()) / 'download-report.json' for line in result.stdout.splitlines()
        if line.strip() and Path(line.strip()).is_absolute()]
    reports = [path.resolve() for path in reports if path.is_file() and path.resolve().is_relative_to(root)]
    if len(reports) != 1:
        raise RuntimeError('未找到唯一的下载报告；请检查下载目录。')
    report = json.loads(reports[0].read_text(encoding='utf-8'))
    paths = [Path(name).resolve() for record in report.get('records', []) if record.get('status') == 'ok'
        for name in record.get('files', [])]
    paths = [path for path in paths if path.is_file() and path.is_relative_to(root)
        and path.suffix.lower() in {'.mp4', '.webm', '.mov', '.m4v', '.mkv', '.flv', '.ogv'}]
    if not paths:
        raise RuntimeError('下载报告中没有可分析的视频文件；请检查报告。')
    # The upstream WeChat Channels route writes both H.264 and H.265; prefer H.264 for preview.
    return sorted(paths, key=lambda path: ('h265' in path.name.lower(), path.name))[0]


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == 'doctor':
        from doctor import main as doctor_main
        return doctor_main()
    if argv and argv[0] == 'download':
        env = dict(os.environ)
        env['PATH'] = str(Path(sys.executable).parent) + os.pathsep + env.get('PATH', '')
        return subprocess.run([sys.executable, str(Path(__file__).with_name('download_video.py')), *argv[1:]], env=env).returncode
    parser = argparse.ArgumentParser(description='Download or analyze one video with local Whisper and Codex CLI.',
        epilog='Extra options are forwarded to video_study.py; use --analysis-help for the full list.')
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--video', help='Local video path')
    source.add_argument('--url', help='Single video URL; uses the original z-video-downloader implementation')
    parser.add_argument('--download-root', default=str(Path.cwd() / 'Video/Downloads'))
    parser.add_argument('--cookies-file', default='')
    if '--analysis-help' in argv:
        video_study.parse_args(['--help'])
        return 0
    args, remaining = parser.parse_known_args(argv)
    # Validate analysis options before any download starts.
    analysis_args = video_study.parse_args(['--video', args.video or 'downloaded-video', *remaining])
    try:
        video = download(args.url, Path(args.download_root), args.cookies_file, analysis_args.title) if args.url else Path(args.video).expanduser()
    except (ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return video_study.main(['--video', str(video), *remaining])


if __name__ == '__main__':
    raise SystemExit(main())
