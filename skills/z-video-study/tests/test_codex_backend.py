from pathlib import Path
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import codex_backend as backend
import video_study as study


class CodexBackendTests(unittest.TestCase):
    def test_backend_selection_is_not_required(self):
        args = study.parse_args(['--video', 'x.mp4'])
        self.assertFalse(hasattr(args, 'provider'))
        self.assertEqual(args.model, '')

    def test_frame_limit_preserves_end_and_all_frames(self):
        frames = [study.Frame(f'frame-{i}', i * 10.0, '', Path(f'{i}.jpg'), i) for i in range(1, 7)]
        parts = study.segment_frames(frames, 70, max_segments=2)
        self.assertEqual(parts[0][0], 0)
        self.assertEqual(parts[-1][1], 70)
        self.assertEqual([f.frame_id for _, _, selected in parts for f in selected], [f.frame_id for f in frames])
        self.assertEqual(parts[0][1], parts[1][0])

    def test_plain_transcript_uses_total_duration(self):
        self.assertEqual(study.transcript_for_window({'text': '0123456789'}, 2, 4, total_duration=10), '23')
        self.assertEqual(study.transcript_for_window({'text': '0123456789'}, 8, 10, total_duration=10), '89')

    def test_api_keys_and_mail_credentials_excluded_from_child(self):
        values = {'DASHSCOPE_API_KEY': 'private', 'CODEX_API_KEY': 'private', 'OPENAI_API_KEY': 'private',
                  'MAIL_AUTH_CODE': 'private', 'MAIL_ADDR': 'private', 'QWEN_MODEL': 'qwen', 'PATH': '/bin'}
        with patch.dict(os.environ, values, clear=True):
            env = backend.child_environment()
        self.assertEqual(env, {'PATH': '/bin'})

    def test_missing_segment_or_wrong_frame_is_rejected(self):
        section = [{'segment_index': 0, 'frames': [{'frame_id': 'f1'}]}]
        with self.assertRaises(ValueError):
            backend.validate_segments([], section)
        with self.assertRaises(ValueError):
            backend.validate_segments([{'segment_index': 0, 'key_points': [{'frame_id': 'f2'}]}], section)

    def test_cache_requires_same_evidence_and_exec_is_readonly_chatgpt(self):
        calls = []
        class FakeProcess:
            returncode = 0
            def __init__(self, cmd, **kw):
                calls.append((cmd, kw))
                output = Path(cmd[cmd.index('--output-last-message') + 1])
                output.write_text('{"value": "observed"}')
            def communicate(self, *a, **kw):
                return '"a JSON string line, not an event"\n', 'model: test-vision-model\n'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); image = root / 'frame.jpg'; image.write_bytes(b'first')
            params = dict(prompt='Read chart', images=[image], schema=backend.obj({'value': backend.TEXT}),
                          cache=root / 'cache', model='', effort='', timeout=20)
            with patch.object(backend, 'check_login'), patch.object(backend.shutil, 'which', return_value='/bin/codex'), patch.object(backend.subprocess, 'Popen', FakeProcess):
                _, first = backend.run_job(**params)
                _, second = backend.run_job(**params)
                image.write_bytes(b'changed')
                _, third = backend.run_job(**params)
        self.assertFalse(first['cache_hit']); self.assertTrue(second['cache_hit']); self.assertFalse(third['cache_hit'])
        self.assertEqual(len(calls), 2)
        cmd, kw = calls[0]
        self.assertEqual(cmd[cmd.index('--sandbox') + 1], 'read-only')
        self.assertIn('forced_login_method="chatgpt"', cmd)
        self.assertIn('--ignore-user-config', cmd)
        self.assertIn('--image', cmd)
        self.assertNotIn('--dangerously-bypass-approvals-and-sandbox', cmd)
        self.assertNotIn('DASHSCOPE_API_KEY', kw['env'])


if __name__ == '__main__':
    unittest.main()
