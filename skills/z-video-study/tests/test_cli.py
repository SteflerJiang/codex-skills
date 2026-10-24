import contextlib
import io
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

    def test_single_video_and_config_isolation_and_resolved_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root / 'example' / 'example.mp4'
            video.parent.mkdir()
            video.write_bytes(b'local video')
            cookies = root / 'cookies.txt'
            cookies.write_text('# Netscape HTTP Cookie File\n')
            result = subprocess.CompletedProcess([], 0, stdout=str(video) + '\n', stderr='')
            with patch.object(cli.subprocess, 'run', return_value=result) as run:
                actual = cli.download('https://example.com/video', root, str(cookies))
            self.assertEqual(actual, video.resolve())
            command = run.call_args.args[0]
            self.assertIn('--no-playlist', command)
            self.assertIn('--ignore-config', command)
            self.assertEqual(command[command.index('--cookies') + 1], str(cookies.resolve()))
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


if __name__ == '__main__':
    unittest.main()
