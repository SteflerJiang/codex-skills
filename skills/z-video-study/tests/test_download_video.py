from __future__ import annotations

import importlib.util
import json
import re
import socket
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "download_video.py"
SPEC = importlib.util.spec_from_file_location("download_video", SCRIPT)
download_video = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(download_video)


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002, ANN001
        pass


class InvidiousLikeHandler(BaseHTTPRequestHandler):
    payload = b"\x00\x00\x00\x18ftypmp42" + b"video-data" * 4096
    video_id = "v1wZwxY3CMg"

    def log_message(self, format, *args):  # noqa: A002, ANN001
        pass

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == f"/api/v1/videos/{self.video_id}":
            body = json.dumps({"title": "Sample Invidious Video"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/latest_version":
            self.send_response(302)
            self.send_header("Location", f"/companion/latest_version?{parsed.query}")
            self.end_headers()
            return

        if parsed.path == "/companion/latest_version":
            query = parse_qs(parsed.query)
            video_id = (query.get("id") or [""])[0]
            self.send_response(302)
            self.send_header(
                "Location",
                f"/companion/videoplayback?id={video_id}&itag=18&clen={len(self.payload)}&host=unit.test",
            )
            self.end_headers()
            return

        if parsed.path == "/companion/videoplayback":
            match = re.fullmatch(r"bytes=(\d+)-(\d+)", self.headers.get("Range", ""))
            if not match:
                self.send_response(416)
                self.end_headers()
                return
            start, end = (int(match.group(1)), int(match.group(2)))
            end = min(end, len(self.payload) - 1)
            body = self.payload[start : end + 1]
            self.send_response(206)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(self.payload)}")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.end_headers()


class InterruptedVideoHandler(BaseHTTPRequestHandler):
    payload = b"\x00\x00\x00\x18ftypmp42" + b"resumable-video-data" * 4096

    def log_message(self, format, *args):  # noqa: A002, ANN001
        pass

    def do_GET(self):  # noqa: N802
        range_header = self.headers.get("Range", "")
        match = re.fullmatch(r"bytes=(\d+)-", range_header)
        if match:
            start = int(match.group(1))
            body = self.payload[start:]
            self.send_response(206)
            self.send_header("Content-Type", "video/mp4")
            self.send_header(
                "Content-Range",
                f"bytes {start}-{len(self.payload) - 1}/{len(self.payload)}",
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        cutoff = len(self.payload) // 3
        self.send_response(200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(len(self.payload)))
        self.end_headers()
        self.wfile.write(self.payload[:cutoff])
        self.wfile.flush()
        try:
            self.connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.connection.close()


class MissingTotalInvidiousHandler(InvidiousLikeHandler):
    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/companion/videoplayback":
            body = self.payload[:2048]
            self.send_response(206)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


class DownloadVideoTests(unittest.TestCase):
    def test_default_output_root_uses_workspace_when_run_from_repo(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir)
            skill_script = workspace / "z-skills" / "z-video-downloader" / "scripts" / "download_video.py"
            root = download_video.discover_project_root(skill_script, cwd=workspace)
            self.assertEqual(root.resolve(), workspace.resolve())

    def test_project_root_does_not_change_with_external_cwd(self):
        with tempfile.TemporaryDirectory() as workspace_dir, tempfile.TemporaryDirectory() as outside_dir:
            workspace = Path(workspace_dir)
            skill_script = workspace / "z-skills" / "z-video-downloader" / "scripts" / "download_video.py"
            root = download_video.discover_project_root(skill_script, cwd=Path(outside_dir))
            self.assertEqual(root.resolve(), workspace.resolve())

    def test_parse_args_accepts_reusable_run_directory(self):
        args = download_video.parse_args(
            ["--run-dir", "/tmp/existing-video-run", "https://example.com/video.mp4"]
        )
        self.assertEqual(args.run_dir, "/tmp/existing-video-run")

    def test_find_ytdlp_ignores_directories(self):
        original = download_video.YTDLP_CANDIDATES
        download_video.YTDLP_CANDIDATES = [Path(".")]
        try:
            self.assertIsNone(download_video.find_ytdlp())
        finally:
            download_video.YTDLP_CANDIDATES = original

    def test_classify_common_urls(self):
        cases = {
            "https://example.com/video.mp4": "direct",
            "https://cdn.example.com/live/index.m3u8": "stream",
            "https://www.youtube.com/watch?v=BaW_jenozKc": "platform",
            "https://www.bilibili.com/video/BV1xx411c7mD": "platform",
        }
        for url, expected in cases.items():
            with self.subTest(url=url):
                self.assertEqual(download_video.classify_url(url), expected)

    def test_platform_names(self):
        self.assertEqual(download_video.platform_name("https://youtu.be/BaW_jenozKc"), "YouTube")
        self.assertEqual(download_video.platform_name("https://b23.tv/abc123"), "Bilibili")
        self.assertEqual(download_video.platform_name("https://www.douyin.com/video/123"), "Douyin")

    def test_youtube_video_id(self):
        self.assertEqual(download_video.youtube_video_id("https://youtu.be/v1wZwxY3CMg"), "v1wZwxY3CMg")
        self.assertEqual(download_video.youtube_video_id("https://www.youtube.com/watch?v=v1wZwxY3CMg"), "v1wZwxY3CMg")
        self.assertEqual(download_video.youtube_video_id("https://www.youtube.com/shorts/v1wZwxY3CMg"), "v1wZwxY3CMg")
        self.assertEqual(download_video.youtube_video_id("https://example.com/watch?v=v1wZwxY3CMg"), "")

    def test_build_ytdlp_cmd_supports_browser_cookies_when_explicit(self):
        cmd = download_video.build_ytdlp_cmd(
            "https://www.youtube.com/watch?v=BaW_jenozKc",
            Path("/tmp/out"),
            ytdlp=Path("/opt/ytdlp"),
            quality="1080",
            max_video_mb=500,
            browser_cookies="chrome",
            playlist=False,
        )
        self.assertIn("--cookies-from-browser", cmd)
        self.assertIn("chrome", cmd)
        self.assertIn("--no-playlist", cmd)
        self.assertIn("bv*[height<=1080]+ba/b[height<=1080]/b", cmd)
        self.assertIn("--merge-output-format", cmd)
        self.assertIn("mp4", cmd)
        self.assertIn("--ignore-config", cmd)
        self.assertIn("--continue", cmd)
        self.assertIn("--part", cmd)
        self.assertIn("--concurrent-fragments", cmd)
        self.assertIn("4", cmd)

    def test_build_ytdlp_cmd_supports_subtitles_thumbnail_and_archive(self):
        cmd = download_video.build_ytdlp_cmd(
            "https://www.youtube.com/watch?v=BaW_jenozKc",
            Path("/tmp/out"),
            ytdlp=Path("/opt/ytdlp"),
            quality="1080",
            max_video_mb=500,
            subtitles=True,
            subtitle_langs="zh.*,en.*",
            embed_thumbnail=True,
            download_archive="/tmp/video-archive.txt",
        )
        self.assertIn("--write-subs", cmd)
        self.assertIn("--write-auto-subs", cmd)
        self.assertIn("--sub-langs", cmd)
        self.assertIn("zh.*,en.*", cmd)
        self.assertIn("--embed-thumbnail", cmd)
        self.assertIn("--download-archive", cmd)
        self.assertIn("/tmp/video-archive.txt", cmd)

    def test_build_ytdlp_cmd_preserves_fractional_size_limit(self):
        cmd = download_video.build_ytdlp_cmd(
            "https://www.youtube.com/watch?v=BaW_jenozKc",
            Path("/tmp/out"),
            ytdlp=Path("/opt/ytdlp"),
            quality="720",
            max_video_mb=0.5,
        )
        index = cmd.index("--max-filesize")
        self.assertEqual(cmd[index + 1], "524288")

    def test_format_selector_rejects_non_positive_height(self):
        with self.assertRaisesRegex(ValueError, "positive"):
            download_video.format_selector("0")

    def test_ytdlp_archive_hit_is_reported_as_skipped_without_output_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            class Completed:
                returncode = 0
                stdout = ""
                stderr = ""

            with patch.object(download_video.subprocess, "run", return_value=Completed()):
                record = download_video.download_with_ytdlp(
                    "https://www.youtube.com/watch?v=BaW_jenozKc",
                    Path(tmp_dir),
                    ytdlp=Path("/opt/ytdlp"),
                    quality="1080",
                    max_video_mb=500,
                    download_archive="/tmp/archive.txt",
                )
            self.assertEqual(record["status"], "skipped")
            self.assertIn("archive", record["note"])

    def test_build_ytdlp_cmd_prefers_cookies_file(self):
        cmd = download_video.build_ytdlp_cmd(
            "https://www.youtube.com/watch?v=BaW_jenozKc",
            Path("/tmp/out"),
            ytdlp=Path("/opt/ytdlp"),
            quality="1080",
            max_video_mb=500,
            cookies_file="/tmp/cookies.txt",
            browser_cookies="chrome",
            playlist=False,
        )
        self.assertIn("--cookies", cmd)
        self.assertIn("/tmp/cookies.txt", cmd)
        self.assertNotIn("--cookies-from-browser", cmd)
        self.assertNotIn("chrome", cmd)

    def test_direct_download_from_local_http_server(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as out_dir:
            source = Path(source_dir)
            payload = b"fake mp4 bytes"
            (source / "sample.mp4").write_bytes(payload)
            server = ThreadingHTTPServer(("127.0.0.1", 0), lambda *args, **kwargs: QuietHandler(*args, directory=source_dir, **kwargs))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f"http://127.0.0.1:{server.server_address[1]}/sample.mp4"
                record = download_video.download_direct_video(
                    download_video.requests.Session(),
                    url,
                    Path(out_dir),
                    max_video_mb=1,
                )
                self.assertEqual(record["status"], "ok")
                self.assertEqual(record["bytes"], len(payload))
                self.assertEqual(Path(record["files"][0]).read_bytes(), payload)
            finally:
                server.shutdown()
                server.server_close()

    def test_direct_download_resumes_from_partial_file(self):
        with tempfile.TemporaryDirectory() as out_dir:
            server = ThreadingHTTPServer(("127.0.0.1", 0), InterruptedVideoHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f"http://127.0.0.1:{server.server_address[1]}/resume.mp4"
                first = download_video.download_direct_video(
                    download_video.requests.Session(),
                    url,
                    Path(out_dir),
                    max_video_mb=1,
                )
                self.assertEqual(first["status"], "failed")
                partial = Path(out_dir, "resume.mp4.part")
                self.assertTrue(partial.exists())
                self.assertGreater(partial.stat().st_size, 0)

                second = download_video.download_direct_video(
                    download_video.requests.Session(),
                    url,
                    Path(out_dir),
                    max_video_mb=1,
                )
                self.assertEqual(second["status"], "ok")
                self.assertEqual(
                    Path(second["files"][0]).read_bytes(),
                    InterruptedVideoHandler.payload,
                )
                self.assertFalse(partial.exists())
            finally:
                server.shutdown()
                server.server_close()

    def test_collect_input_urls_reads_inventory_and_text_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            inventory = tmp / "04-media-inventory.md"
            inventory.write_text(
                "\n".join(
                    [
                        "| Status | Kind | Page | Download Skill | Source URL | Note |",
                        "| --- | --- | --- | --- | --- | --- |",
                        "| detected | platform | MAIN-01.md | z-video-downloader | https://youtu.be/BaW_jenozKc | |",
                        "| detected | direct | MAIN-01.md | z-video-downloader | https://cdn.example.com/a.mp4 | |",
                    ]
                ),
                encoding="utf-8",
            )
            url_file = tmp / "urls.txt"
            url_file.write_text(
                "# one URL per line\nhttps://cdn.example.com/a.mp4\nhttps://vimeo.com/123456\n",
                encoding="utf-8",
            )
            urls = download_video.collect_input_urls(
                ["https://youtu.be/BaW_jenozKc"],
                url_files=[url_file],
                inventories=[inventory],
            )
            self.assertEqual(
                urls,
                [
                    "https://youtu.be/BaW_jenozKc",
                    "https://cdn.example.com/a.mp4",
                    "https://vimeo.com/123456",
                ],
            )

    def test_collect_input_urls_rejects_empty_input(self):
        with self.assertRaisesRegex(ValueError, "No valid video URLs"):
            download_video.collect_input_urls(["  "], url_files=[], inventories=[])

    def test_collect_input_urls_rejects_non_http_url(self):
        with self.assertRaisesRegex(ValueError, "Unsupported video URL"):
            download_video.collect_input_urls(
                ["file:///tmp/private.mp4"],
                url_files=[],
                inventories=[],
            )

    def test_collect_input_urls_rejects_credentials_and_whitespace(self):
        invalid = [
            "https://user:secret@example.com/video.mp4",
            "https://example.com/video file.mp4",
        ]
        for url in invalid:
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, "Unsafe video URL"):
                download_video.collect_input_urls([url], url_files=[], inventories=[])

    def test_download_archive_skip_is_reported_as_successful_skip(self):
        original_run = download_video.subprocess.run

        def fake_run(*args, **kwargs):
            return subprocess.CompletedProcess(
                args=args[0],
                returncode=0,
                stdout="",
                stderr="[download] sample has already been recorded in the archive",
            )

        download_video.subprocess.run = fake_run
        try:
            with tempfile.TemporaryDirectory() as out_dir:
                record = download_video.download_with_ytdlp(
                    "https://www.youtube.com/watch?v=BaW_jenozKc",
                    Path(out_dir),
                    ytdlp=Path("/opt/ytdlp"),
                    quality="1080",
                    max_video_mb=500,
                    download_archive="/tmp/archive.txt",
                )
                self.assertEqual(record["status"], "skipped")
                download_video.write_reports(Path(out_dir), [record["url"]], [record])
                report = Path(out_dir, "download-report.md").read_text(encoding="utf-8")
                self.assertIn("已跳过：1", report)
                self.assertIn("失败：0", report)
        finally:
            download_video.subprocess.run = original_run

    def test_cookie_authenticated_failure_does_not_use_third_party_fallback(self):
        original_download = download_video.download_with_ytdlp
        original_fallback = download_video.download_youtube_invidious_fallback
        fallback_calls = []

        def fake_download(*args, **kwargs):
            record = download_video.base_record(args[0], "platform")
            record["note"] = "Sign in to confirm you are not a bot"
            return record

        def fake_fallback(*args, **kwargs):
            fallback_calls.append(args[1])
            return download_video.base_record(args[1], "platform-fallback")

        download_video.download_with_ytdlp = fake_download
        download_video.download_youtube_invidious_fallback = fake_fallback
        try:
            download_video.download_one(
                download_video.requests.Session(),
                "https://www.youtube.com/watch?v=BaW_jenozKc",
                Path("/tmp"),
                ytdlp=Path("/opt/ytdlp"),
                quality="1080",
                max_video_mb=500,
                cookies_file="/tmp/cookies.txt",
                browser_cookies="",
                playlist=False,
                prefer_ytdlp=False,
                invidious_fallback=True,
                timeout=5,
            )
            self.assertEqual(fallback_calls, [])
        finally:
            download_video.download_with_ytdlp = original_download
            download_video.download_youtube_invidious_fallback = original_fallback

    def test_invidious_missing_total_is_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as out_dir:
            server = ThreadingHTTPServer(("127.0.0.1", 0), MissingTotalInvidiousHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                instance = f"http://127.0.0.1:{server.server_address[1]}"
                record = download_video.download_youtube_invidious_fallback(
                    download_video.requests.Session(),
                    f"https://youtu.be/{MissingTotalInvidiousHandler.video_id}",
                    Path(out_dir),
                    max_video_mb=1,
                    timeout=5,
                    instances=[instance],
                    chunk_size=4096,
                )
                self.assertEqual(record["status"], "failed")
                self.assertIn("content-range-total-missing", record["note"])
                self.assertEqual(list(Path(out_dir).glob("*.mp4")), [])
            finally:
                server.shutdown()
                server.server_close()

    def test_invidious_fallback_downloads_range_proxy(self):
        with tempfile.TemporaryDirectory() as out_dir:
            server = ThreadingHTTPServer(("127.0.0.1", 0), InvidiousLikeHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                instance = f"http://127.0.0.1:{server.server_address[1]}"
                record = download_video.download_youtube_invidious_fallback(
                    download_video.requests.Session(),
                    f"https://youtu.be/{InvidiousLikeHandler.video_id}",
                    Path(out_dir),
                    max_video_mb=1,
                    timeout=5,
                    instances=[instance],
                    chunk_size=4096,
                )
                self.assertEqual(record["status"], "ok")
                self.assertEqual(record["platform"], "YouTube / Invidious proxy")
                self.assertEqual(Path(record["files"][0]).read_bytes(), InvidiousLikeHandler.payload)
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
