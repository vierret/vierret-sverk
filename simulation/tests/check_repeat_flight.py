#!/usr/bin/env python3
"""Run inside SITL: repeat the user's Python takeoff/landing without restarting PX4."""
import argparse
from pathlib import Path
import subprocess
import sys
import time

import sverk_interfaces


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cycles', type=int, default=2)
    parser.add_argument('--height', type=float, default=2.0)
    parser.add_argument('--pause', type=float, default=5.0)
    args = parser.parse_args()
    drone = sverk_interfaces.init(Nodename='repeat_flight_check')
    try:
        for cycle in range(1, args.cycles + 1):
            print(f'Cycle {cycle}/{args.cycles}: takeoff', flush=True)
            try:
                drone.control.navigate_wait(x=0, y=0, z=args.height, frame_id='body',
                                            auto_arm=True, timeout=45)
                print(f'PASS: cycle {cycle} reached takeoff height', flush=True)
            finally:
                response = drone.control.land()
                if not response.success:
                    raise RuntimeError(f'Landing rejected: {response.message}')
                deadline = time.monotonic() + 45
                while drone.control.get_telemetry().armed:
                    if time.monotonic() >= deadline:
                        raise TimeoutError('Landing did not disarm in 45 seconds')
                    time.sleep(0.2)
            print(f'PASS: cycle {cycle} landed and disarmed', flush=True)
            # Disarm alone is not enough: loss of markers can block the NEXT arm.
            subprocess.run([sys.executable, str(Path(__file__).with_name('check_sitl.py')),
                            '--timeout', '15'], check=True)
            print(f'PASS: cycle {cycle} ready for next flight', flush=True)
            if cycle < args.cycles:
                time.sleep(args.pause)
    finally:
        drone.close()


if __name__ == '__main__':
    main()
