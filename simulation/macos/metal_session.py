#!/usr/bin/env python3
"""Run the complete Metal SITL session in one foreground terminal."""
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import metal_sim as metal

COMPOSE = metal.HERE.parent / 'compose'
WRAPPER = COMPOSE / 'sim.sh'
LOGS = metal.BUILD / 'logs'


def stop_group(process):
    """Stop the process tree, including children left after the parent exits."""
    for sig, timeout in ((signal.SIGINT, 10), (signal.SIGTERM, 3), (signal.SIGKILL, 2)):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            break
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            continue
        # Reap the leader but also terminate surviving children on the next pass.
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            break


def session():
    metal.BUILD.mkdir(parents=True, exist_ok=True)
    with (metal.BUILD / 'session.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Metal уже запущен. Остановите его через Ctrl+C в первом терминале.')
        run_session()


def run_session():
    if not metal.shutil.which('gz'):
        raise RuntimeError('Не найден Gazebo. Установите: brew install osrf/simulation/gz-sim8')
    try:
        metal.run(['docker', 'info'], capture_output=True, timeout=20)
    except subprocess.SubprocessError as error:
        raise RuntimeError('Откройте Docker Desktop, дождитесь запуска Engine и повторите команду.') from error
    existing = metal.run(['docker', 'ps', '-aq', '--filter', 'name=^/sverk_sitl$'],
                         capture_output=True, text=True).stdout.strip()
    if existing:
        raise RuntimeError('Контейнер sverk_sitl уже существует. Сначала остановите предыдущий режим '
                           'командой ./sim.sh down с его режимом и Compose project.')
    LOGS.mkdir(parents=True, exist_ok=True)
    processes, files = [], []
    container_owned = False

    def stage(message):
        print(message, flush=True)

    def launch(name, command):
        output = (LOGS / (name + '.log')).open('w')
        files.append(output)
        process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        processes.append((name, process))
        return process

    def alive():
        for name, process in processes:
            if process.poll() is not None:
                raise RuntimeError(f'{name} завершился (код {process.returncode}). Журнал: {LOGS / (name + ".log")}')

    try:
        stage('1/5 Подготовка Docker и ресурсов…')
        if not (COMPOSE / '.env').exists():
            metal.shutil.copyfile(COMPOSE / '.env.example', COMPOSE / '.env')
        config = metal.run(['docker', 'compose', '-f', 'docker-compose.sim.yml',
                            '-f', 'docker-compose.sim.macos.yml', '-f', 'docker-compose.sim.metal.yml',
                            'config', '--format', 'json'], cwd=COMPOSE, capture_output=True, text=True)
        image = json.loads(config.stdout)['services']['sitl']['image']
        image_id = subprocess.run(['docker', 'image', 'inspect', image, '--format', '{{.Id}}'],
                                  capture_output=True, text=True)
        if image_id.returncode:
            metal.run([WRAPPER, 'pull', 'metal'])
            image_id = metal.run(['docker', 'image', 'inspect', image, '--format', '{{.Id}}'],
                                 capture_output=True, text=True)
        stamp = metal.ASSETS / '.image-id'
        if (not stamp.exists() or stamp.read_text().strip() != image_id.stdout.strip()
                or not (metal.ASSETS / 'worlds/obrik_aruco.sdf').exists()):
            metal.assets(image)
            stamp.write_text(image_id.stdout.strip())
        # Mark ownership before up so a partially created container is cleaned up.
        container_owned = True
        with (LOGS / 'docker.log').open('w') as output:
            metal.run([WRAPPER, 'up', 'metal'], stdout=output, stderr=subprocess.STDOUT)
        stage('2/5 Запуск сервера Gazebo с Metal…')
        launch('server', [sys.executable, str(metal.HERE / 'metal_sim.py'), 'server'])
        deadline = time.monotonic() + 120
        with (LOGS / 'network.log').open('w') as output:
            while True:
                alive()
                result = subprocess.run([sys.executable, str(metal.HERE / 'metal_sim.py'), 'network-check'],
                                        stdout=output, stderr=subprocess.STDOUT, timeout=40)
                if result.returncode == 0:
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError('Нет связи с Gazebo. Включите Docker Desktop → Settings → Resources '
                                       '→ Network → Enable host networking → Apply & restart.')
                time.sleep(1)
        stage('3/5 Открытие окна Gazebo…')
        launch('gui', [sys.executable, str(metal.HERE / 'metal_sim.py'), 'gui'])
        stage('4/5 Запуск PX4 и ROS…')
        launch('ros', ['docker', 'exec', 'sverk_sitl', 'bash', '-ic',
                      'ros2 launch launch_system full_system_sitl.launch.py '
                      'external_gazebo:=true use_sim_time:=true obrik_config:=base gz_world:=obrik_aruco'])
        metal.run(['docker', 'cp', metal.HERE.parent / 'tests/check_sitl.py', 'sverk_sitl:/tmp/check_sitl.py'],
                  capture_output=True)
        stage('5/5 Ожидание камеры, ArUco и готовности PX4…')
        ready = launch('ready', ['docker', 'exec', 'sverk_sitl', 'bash', '-ic',
                                'python3 /tmp/check_sitl.py --timeout 120'])
        while ready.poll() is None:
            # The readiness check is expected to exit; all other processes must stay alive.
            for name, process in processes[:-1]:
                if process.poll() is not None:
                    raise RuntimeError(f'{name} завершился. См. {LOGS / (name + ".log")}')
            time.sleep(0.2)
        processes.remove(('ready', ready))
        if ready.returncode:
            raise RuntimeError(f'Проверка готовности не прошла. См. {LOGS / "ready.log"} и {LOGS / "ros.log"}')
        stage(f'Симулятор готов. Окно Gazebo открыто. Для остановки нажмите Ctrl+C.\nЖурналы: {LOGS}')
        while True:
            alive()
            time.sleep(0.5)
    except KeyboardInterrupt:
        stage('\nОстановка симулятора…')
    finally:
        # Finish cleanup even if Ctrl+C is pressed again.
        previous = signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            if container_owned:
                try:
                    subprocess.run(['docker', 'exec', 'sverk_sitl', 'pkill', '-INT', '-f',
                                    '^/usr/bin/python3 /opt/ros/humble/bin/ros2 launch launch_system'],
                                   capture_output=True, timeout=10)
                except (OSError, subprocess.TimeoutExpired):
                    # Still stop native processes and attempt Compose cleanup.
                    pass
            for _, process in reversed(processes):
                stop_group(process)
            if container_owned:
                with (LOGS / 'shutdown.log').open('w') as output:
                    result = subprocess.run([WRAPPER, 'down', 'metal'], stdout=output,
                                            stderr=subprocess.STDOUT, timeout=60)
                if result.returncode:
                    print(f'Не удалось остановить контейнер. См. {LOGS / "shutdown.log"}', file=sys.stderr)
        finally:
            for output in files:
                output.close()
            signal.signal(signal.SIGINT, previous)


if __name__ == '__main__':
    try:
        def terminate(*_):
            raise KeyboardInterrupt

        signal.signal(signal.SIGTERM, terminate)
        if metal.platform.system() != 'Darwin' or metal.platform.machine() != 'arm64':
            raise RuntimeError('Metal запускается на Mac с Apple Silicon, вне Docker/Rosetta.')
        session()
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(f'Ошибка: {error}\nЖурналы запуска: {LOGS}', file=sys.stderr)
        sys.exit(1)
