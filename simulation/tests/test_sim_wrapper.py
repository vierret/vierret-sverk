"""Run the actual Bash wrapper with an isolated project and a Docker recorder."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


COMPOSE = Path(__file__).resolve().parents[1] / 'compose'


class SimWrapperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='sitl-wrapper-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        shutil.copytree(COMPOSE, self.root / 'compose', ignore=shutil.ignore_patterns('.env'))
        self.calls = self.root / 'calls'
        docker = self.root / 'docker'
        docker.write_text('#!/bin/bash\nprintf "%s\\n" "$*" >> "$DOCKER_CALLS"\nexit "${DOCKER_EXIT:-0}"\n')
        docker.chmod(0o755)
        self.env = dict(os.environ, PATH=f'{self.root}:' + os.environ['PATH'],
                        DOCKER_CALLS=str(self.calls), SIM_MACOS_COMPAT='0')

    def run_sim(self, *args, **env):
        return subprocess.run(['bash', str(self.root / 'compose/sim.sh'), *args],
                              env=dict(self.env, **env), capture_output=True, text=True)

    def test_fresh_checkout_can_pull(self):
        result = self.run_sim('pull')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('docker-compose.sim.novnc.yml pull', self.calls.read_text())
        self.assertTrue((self.root / 'compose/.env').exists())

    def test_start_metal_delegates_to_session_without_starting_container_twice(self):
        python = self.root / 'python3'
        python.write_text('#!/bin/bash\nprintf "%s\\n" "$*" > "$DOCKER_CALLS"\n')
        python.chmod(0o755)
        result = self.run_sim('start', 'metal')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls.read_text().strip(), '../macos/metal_session.py')
        self.assertFalse((self.root / 'compose/.env').exists())

    def test_rejects_invalid_arguments_before_docker(self):
        (self.root / 'compose/.env').touch()
        for args in [('up', 'invalid'), ('up', 'novnc', 'ide'),
                     ('up', 'headless', 'invalid'), ('invalid',),
                     ('up', 'headless', '+'), ('up', 'headless', 'ide++mcp'),
                     ('start', 'novnc'), ('start', 'metal', 'mcp'),
                     ('up', 'novnc', 'mcp', 'ignored')]:
            with self.subTest(args=args):
                result = self.run_sim(*args)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.calls.exists(), result.stdout)

    def test_all_modes_and_addons(self):
        (self.root / 'compose/.env').touch()
        for mode in ('novnc', 'headless', 'wslg-nvidia', 'wslg-intel', 'linux-host'):
            addons = ('', 'mcp') if mode == 'novnc' else ('', 'mcp', 'ide', 'ide+mcp')
            for addon in addons:
                with self.subTest(mode=mode, addon=addon):
                    self.assertEqual(self.run_sim('pull', mode, addon).returncode, 0)
                    call = self.calls.read_text().splitlines()[-1]
                    self.assertIn('docker-compose.sim.yml', call)
                    for name in addon.split('+'):
                        if name:
                            self.assertIn(f'docker-compose.sim.{name}.yml', call)

    def test_docker_failure_does_not_report_success(self):
        (self.root / 'compose/.env').touch()
        result = self.run_sim('up', 'novnc', DOCKER_EXIT='17')
        self.assertEqual(result.returncode, 17)
        self.assertNotIn('http://', result.stdout)

    def test_shell_does_not_need_env(self):
        result = self.run_sim('shell')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / 'compose/.env').exists())
        self.assertEqual(self.calls.read_text().strip(), 'exec -it sverk_sitl bash')

    def test_macos_overlay_and_build(self):
        (self.root / 'compose/.env').touch()
        result = self.run_sim('up', 'novnc', SIM_MACOS_COMPAT='1')
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls.read_text().splitlines()
        self.assertIn('docker-compose.sim.macos.yml', calls[0])
        self.assertIn('/opt/sverk/sitl-compat/build.sh', calls[1])

    def test_failed_compat_build_does_not_report_ready(self):
        (self.root / 'compose/.env').touch()
        docker = self.root / 'docker'
        docker.write_text('#!/bin/bash\ncase " $* " in *" exec "*) exit 19 ;; esac\n')
        result = self.run_sim('up', 'novnc', SIM_MACOS_COMPAT='1')
        self.assertEqual(result.returncode, 19)
        self.assertNotIn('http://', result.stdout)

    def test_metal_uses_host_overlay_and_rejects_addons(self):
        (self.root / 'compose/.env').touch()
        result = self.run_sim('up', 'metal', SIM_MACOS_COMPAT='1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('docker-compose.sim.metal.yml', self.calls.read_text())
        self.calls.unlink()
        result = self.run_sim('up', 'metal', 'mcp', SIM_MACOS_COMPAT='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.calls.exists())


if __name__ == '__main__':
    unittest.main()
