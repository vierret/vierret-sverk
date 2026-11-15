#!/usr/bin/env python3
"""Experimental native Gazebo Harmonic / Metal tools for Apple Silicon."""
import argparse
import base64
import json
import os
from pathlib import Path
import platform
import re
import signal
import socket
import shlex
import shutil
import subprocess
import struct
import sys
import time
import zlib

HERE = Path(__file__).resolve().parent
BUILD = HERE / 'build'
ASSETS = BUILD / 'assets'


def run(command, **kwargs):
    print('+', shlex.join(map(str, command)), flush=True)
    return subprocess.run(list(map(str, command)), check=True, **kwargs)


def native_environment():
    env = dict(os.environ)
    for name in ('DISPLAY', 'GALLIUM_DRIVER', 'LIBGL_ALWAYS_SOFTWARE', 'LD_PRELOAD',
                 'QT_QUICK_BACKEND', 'QSG_RHI_BACKEND', 'QT_QPA_PLATFORM'):
        env.pop(name, None)
    env['GZ_PARTITION'] = env.get('SVERK_METAL_PARTITION', 'sverk-metal')
    # Keep native discovery off VPN / Wi-Fi interfaces. Desktop Transport
    # reachability must still pass network-check before PX4 is launched.
    env['GZ_IP'] = env.get('SVERK_METAL_GZ_IP', '127.0.0.1')
    env['GZ_DISCOVERY_MSG_PORT'] = '10317'
    env['GZ_DISCOVERY_SRV_PORT'] = '10318'
    env['GZ_DISCOVERY_MULTICAST_IP'] = '239.255.0.7'
    env.pop('GZ_RELAY', None)
    env['GZ_SIM_RESOURCE_PATH'] = str(ASSETS / 'models') + os.pathsep + str(ASSETS / 'worlds')
    return env


def gazebo_command(kind, world='obrik_aruco'):
    gz = shutil.which('gz')
    if not gz:
        raise RuntimeError('Native gz is missing. Install osrf/simulation/gz-sim8 with Homebrew.')
    common = [gz, 'sim', '-v', '4']
    if kind == 'gui':
        return common + ['-g', '--render-engine-gui', 'ogre2', '--render-engine-gui-api-backend', 'metal']
    world_path = ASSETS / 'worlds' / (world + '.sdf')
    if not world_path.is_file():
        raise RuntimeError(f'Missing world {world_path}; run the assets command first.')
    return common + ['-r', '-s', str(world_path), '--render-engine-server', 'ogre2',
                     '--render-engine-server-api-backend', 'metal']


def stop_process(process):
    if process.poll() is None:
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def server(world):
    command = gazebo_command('server', world)
    # Own the host-side bridge so stopping the server also frees its TCP port.
    bridge = subprocess.Popen([sys.executable, str(HERE / 'discovery_bridge.py'), 'listen'])
    gazebo = None
    try:
        time_limit = time.monotonic() + 5
        port = int(os.environ.get('SVERK_METAL_BRIDGE_PORT', '19090'))
        while time.monotonic() < time_limit:
            if bridge.poll() is not None:
                raise RuntimeError('Host discovery bridge failed to start; check its TCP port.')
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError('Host discovery bridge did not become ready.')
        print('+', shlex.join(command), flush=True)
        gazebo = subprocess.Popen(command, env=native_environment())
        while gazebo.poll() is None:
            if bridge.poll() is not None:
                raise RuntimeError('Host discovery bridge stopped while Gazebo was running.')
            time.sleep(0.2)
        if gazebo.returncode:
            raise subprocess.CalledProcessError(gazebo.returncode, command)
    except KeyboardInterrupt:
        pass
    finally:
        if gazebo is not None:
            stop_process(gazebo)
        stop_process(bridge)


def probe():
    BUILD.mkdir(parents=True, exist_ok=True)
    binary = BUILD / 'metal_probe'
    run(['xcrun', 'clang++', '-std=c++17', '-fobjc-arc', '-Wall', '-Wextra', '-Werror',
         HERE / 'metal_probe.mm', '-framework', 'Foundation', '-framework', 'Metal', '-o', binary])
    run([binary])


def assets(image):
    # Never use or remove the user's running SITL container/home volume.
    BUILD.mkdir(parents=True, exist_ok=True)
    result = run(['docker', 'create', '--platform', 'linux/amd64', '--entrypoint', '/bin/true', image],
                 capture_output=True, text=True)
    container = result.stdout.strip()
    try:
        for directory in ('models', 'worlds'):
            target = ASSETS / directory
            target.mkdir(parents=True, exist_ok=True)
            run(['docker', 'cp', f'{container}:/home/sverk/PX4-Autopilot/Tools/simulation/gz/{directory}/.', target])
    finally:
        run(['docker', 'rm', '-v', container])
    # Resolve paths baked into Linux SDF/material files to their local copies.
    linux_prefix = '/home/sverk/PX4-Autopilot/Tools/simulation/gz'
    for path in ASSETS.rglob('*'):
        if not path.is_symlink() and path.is_file() and path.suffix.lower() in ('.sdf', '.config', '.xml', '.dae', '.mtl', '.material'):
            text = path.read_text()
            if linux_prefix in text:
                path.write_text(text.replace(linux_prefix, str(ASSETS)))
    print(f'Assets copied to {ASSETS}. Linux .so system plugins are not macOS plugins.')


def network_check(world):
    # Test real request/reply and topic payload, not just discovery listings.
    commands = (
        (['gz', 'service', '-s', f'/world/{world}/control', '--reqtype', 'gz.msgs.WorldControl',
          '--reptype', 'gz.msgs.Boolean', '--timeout', '5000', '--req', 'pause: false'], 'data: true'),
        (['timeout', '8s', 'gz', 'topic', '-e', '-t', f'/world/{world}/stats', '-n', '1'], 'real_time_factor'),
    )
    for command, expected in commands:
        result = run(['docker', 'exec', 'sverk_sitl', *command], capture_output=True, text=True, timeout=15)
        if expected not in result.stdout:
            raise RuntimeError(f'Gazebo Transport did not return {expected!r}. '
                               'Check native server, partition and Docker Desktop host networking. '
                               f'Response: {result.stdout.strip()}')
    print('PASS: Docker -> native world control reply and native -> Docker stats payload')


def spawn_base(world):
    model = ASSETS / 'models/x500_obrik_base/model.sdf'
    if not model.is_file():
        raise RuntimeError('Model missing; run assets first.')
    # JSON strings are also valid protobuf quoted strings, including spaces.
    request = (f'sdf_filename: {json.dumps(str(model))}, name: "x500_obrik_base_0", '
               'pose: {position: {x: 0, y: 0.0615, z: 0.3}}')
    result = run([gazebo_command('gui')[0], 'service', '-s', f'/world/{world}/create',
                  '--reqtype', 'gz.msgs.EntityFactory', '--reptype', 'gz.msgs.Boolean',
                  '--timeout', '5000', '--req', request],
                 env=native_environment(), capture_output=True, text=True, timeout=10)
    if 'data: true' not in result.stdout:
        raise RuntimeError(f'Native model creation failed: {result.stdout.strip()}')
    print('Base model spawned for sensor testing. Restart the native server before attaching PX4.')


def save_camera(image, output):
    width, height, step = int(image['width']), int(image['height']), int(image['step'])
    if image.get('pixelFormatType') != 'RGB_INT8' or step != width * 3:
        raise RuntimeError('Expected the base RGB_INT8 camera with tightly packed RGB rows.')
    data = base64.b64decode(image['data'], validate=True)
    if width <= 0 or height <= 0 or len(data) != step * height:
        raise RuntimeError('Camera image dimensions or payload are invalid.')
    stride = 3 * max(1, width * height // 10000)
    colors = {data[i:i+3] for i in range(0, len(data) - 2, stride)}
    if len(colors) < 8:
        raise RuntimeError('Camera frame is uniform/empty; inspect the sensor renderer.')

    def chunk(kind, payload):
        return (struct.pack('>I', len(payload)) + kind + payload
                + struct.pack('>I', zlib.crc32(kind + payload)))

    rows = b''.join(b'\0' + data[y*step:(y+1)*step] for y in range(height))
    png = b'\x89PNG\r\n\x1a\n'
    png += chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b'')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(png)
    print(f'PASS: native camera {width}x{height}, {len(data)} bytes, {len(colors)} sampled colors; {output}')


def camera_check(world, output):
    topic = f'/world/{world}/model/x500_obrik_base_0/link/rpi_camera_link/sensor/imager/image'
    result = run([gazebo_command('gui')[0], 'topic', '-e', '-t', topic, '-n', '1', '--json-output'],
                 env=native_environment(), capture_output=True, text=True, timeout=20)
    save_camera(json.loads(result.stdout), output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('probe', 'doctor', 'assets', 'server', 'gui',
                                           'network-check', 'spawn-base', 'camera-check'))
    parser.add_argument('--world', default='obrik_aruco')
    parser.add_argument('--image', default='ilyawwww/sverk-ros2:v1.9-sim-novnc')
    parser.add_argument('--output', type=Path, default=BUILD / 'camera.png')
    args = parser.parse_args()
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        parser.error('Run natively on an Apple Silicon Mac, outside Docker/Rosetta.')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', args.world):
        parser.error('world must be a world name, not a path')
    if args.command in ('probe', 'doctor'):
        probe()
        if args.command == 'doctor':
            command = gazebo_command('gui')
            result = run([command[0], 'sim', '--versions'], capture_output=True, text=True)
            print(result.stdout.strip())
            if not re.search(r'\b8\.\d+', result.stdout):
                raise RuntimeError('Gazebo Harmonic (sim 8) is required; select the matching gz installation.')
            print('Metal device and native Harmonic found; Docker transport and SITL flight are separate checks.')
    elif args.command == 'assets':
        assets(args.image)
    elif args.command == 'network-check':
        network_check(args.world)
    elif args.command == 'spawn-base':
        spawn_base(args.world)
    elif args.command == 'camera-check':
        camera_check(args.world, args.output)
    elif args.command == 'server':
        server(args.world)
    else:
        command = gazebo_command(args.command, args.world)
        print('Native Gazebo: Metal requested. Confirm Metal in the renderer log; noVNC is not used.', flush=True)
        os.execvpe(command[0], command, native_environment())


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, subprocess.SubprocessError, OSError, ValueError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        sys.exit(1)
