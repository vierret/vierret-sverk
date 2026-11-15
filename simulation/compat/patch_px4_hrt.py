#!/usr/bin/env python3
"""Backport the POSIX HRT recursive-lock fix into the packaged SITL build.

Only drv_hrt.cpp is recompiled. All flight modules and generated messages stay
from the image. Upstream fix: PX4/PX4-Autopilot commit 9b62a1701de211fe8d9021f291d5668e8fb38b4e.
"""
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path('/home/sverk/PX4-Autopilot')
BUILD = ROOT / 'build/px4_sitl_default'
CACHE = Path('/home/sverk/.cache/sverk-px4-hrt')
PATCH = Path(__file__).with_name('px4-hrt-race.patch')
SOURCE_SHA = '9c6c0946dfac2b3629636e759ebeac4081d654dfdd60fb0d763fc9feeb401ba6'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    binary = BUILD / 'bin/px4'
    marker = CACHE / 'installed.json'
    patch_id = digest(PATCH)
    if marker.exists():
        installed = json.loads(marker.read_text())
        if installed == dict(binary=digest(binary), patch=patch_id):
            print('SITL: исправление гонки HRT уже установлено.')
            return
    # Never relink a running PX4 process or an unsupported/missing build tree.
    running = subprocess.run(['pgrep', '-x', 'px4'], capture_output=True)
    if running.returncode == 0:
        raise RuntimeError('Stop PX4 before applying the HRT fix.')
    versions = list(BUILD.rglob('build_git_version.h'))
    if len(versions) != 1 or '78bd1cc7c1e6472e535772d91a3ecbbfa1b5d507' not in versions[0].read_text():
        raise RuntimeError('Unsupported PX4 build for HRT backport; use the documented v1.9-sim image.')
    entries = json.loads((BUILD / 'compile_commands.json').read_text())
    entry, = [e for e in entries if e['file'].endswith('/platforms/posix/src/px4/common/drv_hrt.cpp')]
    archive = CACHE / 'v1.15.4.tar.gz'
    if not archive.exists() or digest(archive) != SOURCE_SHA:
        print('SITL: загрузка исходников PX4 v1.15.4 для исправления таймера (однократно)…', flush=True)
        with urllib.request.urlopen('https://codeload.github.com/PX4/PX4-Autopilot/tar.gz/refs/tags/v1.15.4', timeout=60) as response:
            archive.write_bytes(response.read())
        if digest(archive) != SOURCE_SHA:
            raise RuntimeError('PX4 source checksum mismatch; no installed files changed.')
    source = CACHE / 'PX4-Autopilot-1.15.4'
    # Re-extract the pinned, checksum-verified sources for an idempotent patch.
    with tarfile.open(archive) as tar:
        tar.extractall(CACHE)
    subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(PATCH)], cwd=source, check=True)
    command = shlex.split(entry['command'])
    for i, arg in enumerate(command):
        if str(ROOT) in arg and str(BUILD) not in arg:
            command[i] = arg.replace(str(ROOT), str(source))
    obj = CACHE / 'drv_hrt.cpp.o'
    command[command.index('-o') + 1] = str(obj)
    print('SITL: пересборка POSIX-таймера PX4…', flush=True)
    subprocess.run(command, cwd=BUILD, check=True)
    layer = 'platforms/posix/src/px4/common/libpx4_layer.a'
    patched_layer = CACHE / 'libpx4_layer.a'
    shutil.copyfile(BUILD / layer, patched_layer)
    subprocess.run(['ar', 'r', str(patched_layer), str(obj)], check=True)
    commands = subprocess.check_output(['ninja', '-t', 'commands', 'bin/px4'], cwd=BUILD, text=True)
    link, = [part.strip() for part in commands.split('&&') if ' -o bin/px4 ' in part]
    link_args = shlex.split(link)
    link_args = [str(patched_layer) if arg == layer else arg for arg in link_args]
    candidate = BUILD / 'bin/px4.hrt-new'
    link_args[link_args.index('-o') + 1] = str(candidate)
    subprocess.run(link_args, cwd=BUILD, check=True)
    backup = binary.with_name('px4.before-hrt-fix')
    if not backup.exists():
        shutil.copy2(binary, backup)
    candidate.replace(binary)
    marker.write_text(json.dumps(dict(binary=digest(binary), patch=patch_id)))
    print('SITL: исправление гонки POSIX HRT установлено; проверки армирования сохранены.')


if __name__ == '__main__':
    main()
