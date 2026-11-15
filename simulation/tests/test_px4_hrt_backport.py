"""Backport guards: cache validation and refusal to alter unknown firmware."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / 'compat/patch_px4_hrt.py'
SPEC = importlib.util.spec_from_file_location('hrt_backport', PATH)
backport = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backport)


class HrtBackportTests(unittest.TestCase):
    def test_unknown_firmware_is_left_intact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build, cache = root / 'build', root / 'cache'
            (build / 'bin').mkdir(parents=True)
            binary = build / 'bin/px4'
            binary.write_bytes(b'unknown firmware')
            (build / 'build_git_version.h').write_text('#define PX4_GIT_VERSION_STR "unknown"')
            with patch.object(backport, 'BUILD', build), patch.object(backport, 'CACHE', cache), \
                    patch.object(backport.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)):
                with self.assertRaisesRegex(RuntimeError, 'Unsupported PX4'):
                    backport.main()
            self.assertEqual(binary.read_bytes(), b'unknown firmware')
            self.assertFalse((build / 'bin/px4.before-hrt-fix').exists())

    def test_matching_cache_skips_build_but_replaced_binary_invalidates_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build, cache = root / 'build', root / 'cache'
            (build / 'bin').mkdir(parents=True)
            cache.mkdir()
            binary = build / 'bin/px4'
            binary.write_bytes(b'patched firmware')
            (cache / 'installed.json').write_text(json.dumps(dict(
                binary=backport.digest(binary), patch=backport.digest(backport.PATCH))))
            with patch.object(backport, 'BUILD', build), patch.object(backport, 'CACHE', cache), \
                    patch.object(backport.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)) as run:
                backport.main()
                run.assert_not_called()
                binary.write_bytes(b'updated firmware')
                with self.assertRaisesRegex(RuntimeError, 'Unsupported PX4'):
                    backport.main()
                run.assert_called_once()


if __name__ == '__main__':
    unittest.main()
