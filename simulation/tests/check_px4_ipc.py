#!/usr/bin/env python3
"""Exercise the real PX4 server/client startup seam in the shipped amd64 image."""
import argparse
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', default='ilyawwww/sverk-ros2:v1.9-sim-novnc')
    parser.add_argument('--without-compat', action='store_true')
    args = parser.parse_args()
    compat = Path(__file__).resolve().parents[1] / 'compat'
    command = ['docker', 'run', '--rm', '--platform', 'linux/amd64',
               '--mount', f'type=bind,source={compat},target=/opt/sverk/sitl-compat,readonly',
               '--mount', f'type=bind,source={Path(__file__).resolve().parent},target=/tests,readonly',
               '--entrypoint', 'bash', args.image, '-lc']
    script = """
set -eu
cd /home/sverk/PX4-Autopilot
printf '%s\n' 'px4-param show SYS_AUTOSTART || exit $?' 'echo PX4_IPC_OK' > /tmp/ipc.sh
"""
    if not args.without_compat:
        script += 'bash /opt/sverk/sitl-compat/build.sh\n'
        script += 'export LD_PRELOAD=/tmp/sverk-px4-poll-eintr.so\n'
        script += 'cc -O2 -Wall -Wextra -Werror /tests/check_poll_eintr.c -pthread -o /tmp/check_poll\n'
        script += 'timeout 5s /tmp/check_poll\n'
    script += 'timeout 3s ./build/px4_sitl_default/bin/px4 -d -s /tmp/ipc.sh\n'
    result = subprocess.run(command + [script], capture_output=True, text=True, timeout=45)
    output = result.stdout + result.stderr
    if 'PX4_IPC_OK' not in output or 'error connecting to socket' in output:
        print(output)
        print('FAIL: PX4 startup client cannot reach the server', file=sys.stderr)
        return 1
    if result.returncode not in (0, 124):
        print(output)
        return result.returncode
    print('PASS: PX4 startup client read SYS_AUTOSTART through its Unix socket')
    return 0


if __name__ == '__main__':
    sys.exit(main())
