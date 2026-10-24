import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import cli


class PortableEntryTests(unittest.TestCase):
    def test_invalid_url_stops_before_process_or_output_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'not-created'
            with patch.object(cli.subprocess, 'run') as run:
                with self.assertRaises(ValueError):
                    cli.download('https://account:password@example.com/private', root)
                run.assert_not_called()
            self.assertFalse(root.exists())

    def test_delegates_to_original_downloader_and_reads_its_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root / 'example' / 'example.mp4'
            video.parent.mkdir()
            video.write_bytes(b'local video')
            cookies = root / 'cookies.txt'
            cookies.write_text('# Netscape HTTP Cookie File\n')
            (video.parent / 'download-report.json').write_text(json.dumps({'records': [
                {'status': 'ok', 'files': [str(video)]}]}))
            result = subprocess.CompletedProcess([], 0, stdout=str(video.parent) + '\nvideos_ok=1\n', stderr='')
            with patch.object(cli.subprocess, 'run', return_value=result) as run:
                actual = cli.download('https://example.com/video', root, str(cookies))
            self.assertEqual(actual, video.resolve())
            command = run.call_args.args[0]
            self.assertTrue(command[1].endswith('/scripts/download_video.py'))
            self.assertNotIn('--playlist', command)
            self.assertEqual(command[command.index('--cookies-file') + 1], str(cookies.resolve()))
            self.assertTrue((video.parent / 'download-report.json').is_file())

    def test_unknown_analysis_flag_prevents_download(self):
        with patch.object(cli, 'download') as download, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                cli.main(['--url', 'https://example.com/video', '--provider', 'qwen'])
            download.assert_not_called()

    def test_existing_video_passes_options_without_downloading(self):
        with patch.object(cli, 'download') as download, patch.object(cli.video_study, 'main', return_value=0) as analyze:
            self.assertEqual(cli.main(['--video', 'local.mp4', '--frame-count', '8']), 0)
            download.assert_not_called()
            self.assertEqual(analyze.call_args.args[0], ['--video', 'local.mp4', '--frame-count', '8'])

    def test_download_only_forwards_original_options_without_analysis(self):
        result = subprocess.CompletedProcess([], 0)
        with patch.object(cli.subprocess, 'run', return_value=result) as run, patch.object(cli.video_study, 'main') as analyze:
            self.assertEqual(cli.main(['download', '--quality', 'best', '--subtitles', 'https://example.com/video']), 0)
            command = run.call_args.args[0]
            self.assertTrue(command[1].endswith('/scripts/download_video.py'))
            self.assertEqual(command[2:], ['--quality', 'best', '--subtitles', 'https://example.com/video'])
            analyze.assert_not_called()

    def test_video_channels_prefers_h264_from_original_multi_file_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            files = [root / 'video-h265.mp4', root / 'video-h264.mp4']
            for file in files:
                file.write_bytes(b'local video')
            (root / 'download-report.json').write_text(json.dumps({'records': [
                {'status': 'ok', 'files': [str(file) for file in files]}]}))
            result = subprocess.CompletedProcess([], 0, stdout='[1/1] https://example.com/video?token=' + 'x' * 600 + '\n' + str(root) + '\nvideos_ok=1\n', stderr='')
            with patch.object(cli.subprocess, 'run', return_value=result):
                self.assertEqual(cli.download('https://example.com/video', root), files[1])


if __name__ == '__main__':
    unittest.main()
