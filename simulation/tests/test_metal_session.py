"""Session lifecycle tests using real subprocesses, without Docker or Metal."""
import importlib.util
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

MACOS = Path(__file__).resolve().parents[1] / 'macos'
sys.path.insert(0, str(MACOS))
SPEC = importlib.util.spec_from_file_location('metal_session', MACOS / 'metal_session.py')
session = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(session)


class MetalSessionTests(unittest.TestCase):
    def test_interrupt_waits_for_process_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            ready = Path(tmp) / 'ready'
            cleaned = Path(tmp) / 'cleaned'
            source = (
                'import signal,time\n'
                'from pathlib import Path\n'
                'def stop(*_):\n'
                f' Path({str(cleaned)!r}).touch()\n'
                ' raise SystemExit(0)\n'
                'signal.signal(signal.SIGINT,stop)\n'
                f'Path({str(ready)!r}).touch()\n'
                'while True: time.sleep(.1)\n'
            )
            process = subprocess.Popen([sys.executable, '-c', source], start_new_session=True)
            try:
                deadline = time.monotonic() + 5
                while not ready.exists() and time.monotonic() < deadline:
                    time.sleep(.02)
                self.assertTrue(ready.exists())
                session.stop_group(process)
                self.assertEqual(process.returncode, 0)
                self.assertTrue(cleaned.exists())
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()

    def test_active_session_lock_rejects_second_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            build = Path(tmp)
            with (build / 'session.lock').open('w') as lock:
                session.fcntl.flock(lock, session.fcntl.LOCK_EX | session.fcntl.LOCK_NB)
                with patch.object(session.metal, 'BUILD', build), patch.object(session, 'run_session') as run:
                    with self.assertRaisesRegex(RuntimeError, 'уже запущен'):
                        session.session()
                    run.assert_not_called()
            with patch.object(session.metal, 'BUILD', build), patch.object(session, 'run_session') as run:
                session.session()
                run.assert_called_once()

    def test_existing_container_is_not_taken_over(self):
        def run(command, **kwargs):
            return subprocess.CompletedProcess(command, 0, stdout='existing-container\n')
        with patch.object(session.metal.shutil, 'which', return_value='/native/gz'), \
                patch.object(session.metal, 'run', side_effect=run) as calls:
            with self.assertRaisesRegex(RuntimeError, 'уже существует'):
                session.run_session()
        self.assertEqual(len(calls.call_args_list), 2)
        self.assertEqual(calls.call_args_list[-1].args[0][1:3], ['ps', '-aq'])


if __name__ == '__main__':
    unittest.main()
