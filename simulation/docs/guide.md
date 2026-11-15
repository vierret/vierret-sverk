# SVERK SITL: установка и первый полёт

Ниже — установка для **Mac с Apple Silicon** с двумя вариантами графики:

- **Metal / GPU** — нативное окно Gazebo на Mac; установка и весь запуск
  находятся в [разделе Metal](#macos-metal). Режим экспериментальный.
- **noVNC / CPU** — окно Gazebo в браузере; после общей подготовки
  выполняйте разделы 2–3.

Начните с общей подготовки в разделе 1, затем выберите один вариант.
Одновременно запускать оба режима не нужно.
Выполняйте команды по одной, сверху вниз. Каждая команда находится в отдельном
блоке: её можно скопировать целиком. Символы приглашения терминала (`$`, `%`)
вводить не нужно.

Потребуются Docker Desktop, около 7 GB под образ и дополнительное место под
рабочий том и логи. В проверке Docker было выделено 10 CPU и около 8 GiB RAM;
это параметры проверки, а не измеренный минимум. Образ — Linux amd64,
в noVNC картинка считается на CPU, в Metal — на GPU Mac. Для Metal дополнительно
нужны Homebrew, Xcode Command Line Tools и место под нативный Gazebo. Стек: PX4 v1.15.4, Gazebo Harmonic, ROS 2 Humble.

## 1. Подготовить Mac — терминал № 1

### 1.1. Запустить Docker Desktop

Если Docker Desktop не установлен, установите версию для Apple Silicon с
[официального сайта](https://docs.docker.com/desktop/setup/install/mac-install/).
Откройте приложение **Docker** и дождитесь запуска Engine.

Откройте приложение **Терминал** на Mac. Это будет **терминал № 1**.
Пока все команды выполняются **на Mac**, а не внутри контейнера.

Проверьте Docker:

```bash
docker version
```

Должны отображаться обе секции: `Client` и `Server`. Если секции `Server` нет,
сначала дождитесь запуска Docker Desktop.

Проверьте Compose:

```bash
docker compose version
```

Должна появиться версия Compose, а не `unknown command`.

### 1.2. Открыть папку проекта

Инструкция предполагает, что проект находится в `~/vierret-sverk`.
Если он уже скачан в другое место, используйте его фактический путь.
Повторно клонировать существующий проект не нужно.

**Только если проекта ещё нет**, выполните эти две команды по очереди:

```bash
cd ~
```

```bash
git clone https://github.com/vierret/vierret-sverk.git
```

Перейдите в папку запуска симулятора. Эту команду выполняют и при первом,
и при повторном запуске:

```bash
cd ~/vierret-sverk/simulation/compose
```

Проверьте текущую папку:

```bash
pwd
```

Путь должен заканчиваться на `/vierret-sverk/simulation/compose`.
Нужна актуальная полная копия репозитория: одной папки `compose` для Mac недостаточно.

<a id="macos-metal"></a>

## Установка и запуск с GPU на Apple Silicon — Metal

В этом варианте сервер Gazebo, камера и окно используют **OGRE 2 → Metal**
нативно на Mac. PX4 и ROS работают в Docker. Физика и обработка ArUco остаются
на CPU. MPS отдельно устанавливать не нужно: для рендера используется Metal.

На Apple M5 проверены изображение камеры 1280×960, ArUco handoff, взлёт и
посадка с disarm. Остаются задержки VIO и предупреждения PX4 после посадки;
длительная стабильность и ускорение относительно CPU пока не подтверждены.
Пока используйте модель `base`: Linux-плагины LED/servo/spray/optical-flow
в нативном Gazebo не загружаются. Аддоны `ide` и `mcp` в режиме `metal`
обёрткой не поддерживаются.

### M1. Установить зависимости — терминал № 1, на Mac

Сначала выполните общую подготовку из раздела 1. Нужен Docker Compose 2.24.4+
с поддержкой `!reset`. Для установки нативных компонентов нужны
[Homebrew](https://brew.sh/) и Xcode Command Line Tools.
Если Command Line Tools ещё не установлены, вызовите установщик и дождитесь
его завершения в открывшемся окне:

```bash
xcode-select --install
```

Если инструменты уже установлены, повторная установка не нужна.
Проверьте наличие Homebrew:

```bash
brew --version
```

Подключите tap Gazebo:

```bash
brew tap osrf/simulation
```

Разрешите tap, если этого требует ваша версия Homebrew:

```bash
brew trust osrf/simulation
```

Установите Gazebo Harmonic:

```bash
brew install osrf/simulation/gz-sim8
```

В проверке использовался `gz-sim8` 8.15.0 arm64. Поддержка Harmonic на macOS
[завершается 10 января 2027 года](https://discourse.openrobotics.org/t/early-end-of-support-of-gazebo-harmonic-fortress-on-macos/59605);
доступность готовых пакетов зависит от macOS и версий зависимостей.

### M2. Включить сеть Docker — приложение Docker Desktop

Откройте **Settings → Resources → Network → Enable host networking**.
Включите настройку и нажмите **Apply & restart**. Дождитесь перезапуска Engine.
При повторном запуске уже включённую настройку менять не нужно.

### M3. Запустить всё — один терминал на Mac

```bash
cd ~/vierret-sverk/simulation/compose
```

```bash
./sim.sh start metal
```

Это одна команда для первого и повторного запуска. Docker Desktop должен
работать. При первом запуске скрипт сам скачает отсутствующий образ и
подготовит модели; это может занять несколько минут. При следующих запусках
подготовленные ресурсы используются повторно.

Скрипт последовательно запускает контейнер, сервер Gazebo, окно с Metal и
PX4/ROS, проверяет связь, VIO, ArUco handoff и доступность полётных сервисов.
В терминале видны пять этапов, а затем **«Симулятор готов»**.
Окно Gazebo откроется автоматически, дрон появится после запуска PX4.
Дополнительные терминалы и ручной `ros2 launch` для запуска не нужны.
Автоматического взлёта при запуске нет.

Если проверка не проходит, скрипт показывает ошибку и останавливает созданные
им процессы и контейнер. Подробные журналы сохраняются в
`simulation/macos/build/logs/`: `docker.log`, `server.log`, `gui.log`,
`network.log`, `ros.log`, `ready.log` и `shutdown.log`.
Если уже существует контейнер `sverk_sitl` от другого запуска, сначала
остановите предыдущий режим его командой `./sim.sh down …`.

### M4. Остановить или перезапустить

Нажмите **Ctrl+C в единственном терминале запуска**. Скрипт остановит PX4/ROS,
закроет окно и сервер Gazebo, сетевой мост и удалит контейнер. Данные
`/home/sverk` и локальные ресурсы сохраняются. Дождитесь возвращения
приглашения терминала. Для повторного запуска выполните снова:

```bash
./sim.sh start metal
```

Закрытие окна Gazebo также завершает сессию; обычный способ остановки — Ctrl+C.

### M5. Проверить полёт — необязательно, отдельная вкладка на Mac

Оставьте терминал запуска работающим. После сообщения «Симулятор готов»
можно выполнить автоматический взлёт и посадку **в симуляторе**:

```bash
docker exec sverk_sitl bash -ic 'python3 /tmp/check_sitl.py --timeout 120 --flight'
```

Проверка ожидает взлёт выше 0,75 м, посадку около исходной высоты и disarm.
Для ручного управления используйте сервисы из раздела 7 в отдельной оболочке
контейнера. Перед повторным взлётом снова проверьте готовность: после посадки
метки могут пропасть из кадра. Останавливайте сессию после посадки.

Разделы 2–3 ниже относятся к noVNC и для Metal не нужны.
Низкоуровневые команды, проверка камеры и устройство связи —
в [технических заметках Metal](macos-metal.md).

---

## 2. Скачать образ и поднять noVNC — терминал № 1, на Mac

Скачайте образ. Команда нужна при первой установке или обновлении; при обычном
повторном запуске этот шаг можно пропустить:

```bash
./sim.sh pull
```

Обёртка сама создаст `.env` из `.env.example`, если его ещё нет.
Первое скачивание может занять несколько минут. Дождитесь возвращения
приглашения терминала без ошибки.

Запустите контейнер:

```bash
./sim.sh up novnc
```

На Apple Silicon обёртка автоматически подключает macOS-оверлей и готовит
совместимость PX4. В конце должна появиться ссылка `http://localhost:6080/vnc.html`.
Появление ссылки означает готовность рабочего стола; сам симулятор запускается
следующей командой в контейнере.

## 3. Открыть симулятор, проверить и полететь

### 3.1. Открыть noVNC — браузер на Mac

Откройте **[рабочий стол noVNC](http://localhost:6080/vnc.html?autoconnect=1&resize=scale)**.
Если показана кнопка **Connect**, нажмите её. Пароль не нужен.

До запуска Gazebo рабочий стол может быть пустым. Оставьте вкладку открытой
и вернитесь в терминал № 1.

### 3.2. Войти в контейнер — терминал № 1, пока ещё на Mac

```bash
./sim.sh shell
```

Приглашение изменится примерно на `sverk@…:~$`. Это означает, что вы **внутри
контейнера**. Команды `./sim.sh ...` здесь больше вводить не нужно.

### 3.3. Запустить сцену — терминал № 1, внутри контейнера

Скопируйте всю строку одной командой:

```bash
ros2 launch launch_system full_system_sitl.launch.py use_sim_time:=true vnc_gui:=true obrik_config:=base gz_world:=obrik_aruco
```

Оставьте команду работающей. Терминал будет выводить журналы; возвращения
приглашения сейчас быть не должно.

Переключитесь во вкладку noVNC: должно появиться **окно Gazebo с полем
ArUco и дроном**. На холодном запуске подождите до 1–2 минут.
Если окно меньше рабочего стола, разверните его двойным щелчком по заголовку
`Gazebo Sim`. Поле можно приблизить колесом мыши над 3D-видом.
Чёрный экран при работающем PX4 не означает, что GUI готов.

Для ArUco-навигации дождитесь в терминале № 1 строки:

```text
GPS-to-ArUco handoff complete
```

Одна строка `Ready for takeoff!` ещё не подтверждает готовность ArUco.
Сообщения о создании DDS-топиков — обычный журнал подключения PX4.

### 3.4. Открыть второй терминал — на Mac

Первый терминал с симулятором не закрывайте. Откройте **новое окно или вкладку
Терминала на Mac** — это будет **терминал № 2**.

Перейдите в ту же папку:

```bash
cd ~/vierret-sverk/simulation/compose
```

Скопируйте в контейнер проверку готовности:

```bash
docker cp ../tests/check_sitl.py sverk_sitl:/tmp/check_sitl.py
```

Войдите в контейнер:

```bash
./sim.sh shell
```

Теперь оба терминала находятся внутри контейнера, но в первом работает симулятор,
а второй свободен для команд.

### 3.5. Проверить готовность — терминал № 2, внутри контейнера

```bash
python3 /tmp/check_sitl.py
```

Дождитесь трёх строк `PASS`: визуальная одометрия доходит до PX4, положение
валидно и handoff завершён, сервисы `/navigate` и `/land` доступны.
Если проверка завершилась ошибкой, не переходите к взлёту: смотрите
[раздел устранения проблем](#10-если-что-то-не-так).

### 3.6. Взлететь на 1 метр — терминал № 2, внутри контейнера

```bash
ros2 service call /navigate offboard_interfaces/srv/Navigate "{x: 0.0, y: 0.0, z: 1.0, yaw: 0.0, speed: 0.2, frame_id: 'body', auto_arm: true}"
```

В ответе должно быть `success: true`. Наблюдайте подъём дрона в Gazebo.
Ответ сервиса означает принятие команды; подъём занимает некоторое время.

### 3.7. Посадить дрон — терминал № 2, внутри контейнера

```bash
ros2 service call /land std_srvs/srv/Trigger "{}"
```

Дождитесь посадки. В терминале № 1 появятся `Landing detected` и затем
`Disarmed by landing`. После посадки метки могут оказаться вне кадра;
перед следующим взлётом снова проверьте готовность. При потере меток
перезапустите сцену.

### 3.8. Остановить симулятор

В **терминале № 1** нажмите **Ctrl+C**. Затем в **терминале № 2** выйдите
из контейнера:

```bash
exit
```

Вы снова на Mac, в папке `simulation/compose`. Остановите контейнер:

```bash
./sim.sh down novnc
```

Данные `/home/sverk` сохраняются. При следующем запуске начните с перехода
в `simulation/compose`, затем `./sim.sh up novnc`, входа в контейнер и запуска сцены.

### Windows и Linux

Для noVNC порядок тот же. На Windows вместо `./sim.sh ...` используйте
`.\sim.ps1 ...` в PowerShell; при первом запуске может понадобиться
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.
Ниже описаны дополнительные режимы, модели и диагностика; для первого запуска
на Mac они не нужны.

---

## 4. Другие режимы отображения

Во всех режимах используется один полётный стек. В Metal сервер Gazebo
и рендер сенсоров работают на Mac, в остальных режимах — в контейнере. Выберите строку
под своё железо. Флаг в `ros2 launch` **обязан совпадать** с режимом контейнера.

| Режим | Когда | Поднять (из `compose/`) | Флаг launch | Где картинка |
|---|---|---|---|---|
| **Metal** | GPU Apple Silicon; [установка выше](#macos-metal), эксперимент | `./sim.sh start metal` | задаётся автоматически | нативное окно Mac |
| **noVNC** | CPU-рендер на Mac | `./sim.sh up novnc` | `vnc_gui:=true` | браузер :6080 |
| **WSLg + NVIDIA** | Windows + видеокарта NVIDIA | `./sim.sh up wslg-nvidia` | `wslg_gpu_gui:=true` | окно на рабочем столе |
| **WSLg + Intel Arc** | Windows + Intel Arc | `./sim.sh up wslg-intel` | `wslg_gpu_gui:=true` | окно (часто падает → берите noVNC) |
| **Linux X11** | нативный Linux-десктоп | `./sim.sh up linux-host` | `host_x11_gui:=true` | окно на рабочем столе |
| **headless** | без картинки, только логика | `./sim.sh up headless` | `headless:=true` | нет окна |

**Web-IDE (опция).** Аддон `ide` добавляет к любому режиму, **кроме noVNC и Metal**,
VS Code и терминал прямо в браузере — можно работать без `docker exec`/ssh:

```bash
./sim.sh up headless ide       # Windows: .\sim.ps1 up headless ide
# code-server → http://localhost:5467 ,  терминал → http://localhost:8575
```

Терминал :8575 открывается уже внутри контейнера с загруженным ROS-окружением —
запускайте `ros2 launch ...` прямо там. С noVNC аддон не нужен: в его рабочем
столе :6080 терминал открывается штатно.

**MCP-сервер (опция).** Аддон `mcp` поднимает вторым контейнером ROS 2 MCP
HTTP-сервер на `:8765` — набор инструментов над живым ROS-графом симулятора
(список нод/топиков, echo, вызов сервисов, публикация, чтение параметров).
Сочетается с режимами из таблицы, **кроме Metal**, включая noVNC:

```bash
./sim.sh up novnc mcp          # Windows: .\sim.ps1 up novnc mcp
# несколько аддонов сразу:  ./sim.sh up headless ide+mcp
```

Проверка и использование с хоста:

```bash
curl -s http://localhost:8765/healthz     # {"ok": true, "node_ready": true}
curl -s http://localhost:8765/tools       # список инструментов
curl -s http://localhost:8765/policy      # что сейчас разрешено писать
```

Пишущие инструменты (публикация, вызов сервисов, установка параметров)
ограничены политикой `compose/mcp_policy.yaml` — по умолчанию режим `guarded`
(разрешено только то, что подходит под allow-паттерны). Инструменты чтения
доступны всегда. К `:8765` можно подключить своего LLM-агента.

### WSLg (Windows, GPU-окно)

> Compose с WSLg-оверлеями запускайте **строго изнутри WSL-дистрибутива**
> (`wsl -d Ubuntu-24.04`), а не из PowerShell: бинды `/mnt/wslg`, `/usr/lib/wsl`,
> `/dev/dxg` есть только внутри дистрибутива. `docker exec` в уже поднятый
> контейнер работает откуда угодно.

```bash
# из Ubuntu-24.04, папка compose/
./sim.sh up wslg-nvidia
docker exec -it sverk_sitl bash
ros2 launch launch_system full_system_sitl.launch.py use_sim_time:=true \
  wslg_gpu_gui:=true obrik_config:=base gz_world:=obrik_aruco
```

Используйте именно `wslg_gpu_gui:=true`, **не** `wslg_gui` — последний течёт по
памяти (2–5 ГБ/мин, gz-sim#2873); в compose стоит лимит 10 ГБ как страховка.

### Linux X11 (нативный десктоп)

```bash
xhost +local:docker            # один раз, разрешить X11
./sim.sh up linux-host
docker exec -it sverk_sitl bash
ros2 launch launch_system full_system_sitl.launch.py use_sim_time:=true \
  host_x11_gui:=true obrik_config:=base gz_world:=obrik_aruco
```

### headless (без картинки)

Физика, камера, ArUco и VPE работают — просто нет окна Gazebo. Полезно для
автотестов и слабых машин.

```bash
./sim.sh up headless
docker exec -it sverk_sitl bash
ros2 launch launch_system full_system_sitl.launch.py use_sim_time:=true \
  headless:=true obrik_config:=base gz_world:=obrik_aruco
```

---

## 5. Модели дрона и миры

`obrik_config` выбирает модель (оснащение), `gz_world` — мир (поле). Задаются в
команде `ros2 launch`.

### Модели (`obrik_config`)

| `obrik_config` | Оснащение | ArUco-навигация |
|---|---|---|
| `base` | камера, нижний дальномер, LED | да |
| `lidar` | + 2D-лидар LD19 | да |
| `one_rangefinder` | + доп. дальномер | да |
| `three_rangefinders_30` | + три обзорных дальномера 30° | да |
| `three_rangefinders_45` | + три обзорных дальномера 45° | да |
| `graffiti` | + передний дальномер, servo/спрей | да |
| `graffiti_old` | прежний servo/спрей | да |
| `gigaobrik` | MTF-01 + дальномер (без камеры/ArUco) | нет |
| `x500` / `stock` / `legacy` | штатная модель PX4 | зависит от модели |

### Миры (`gz_world`)

| `gz_world` | Поле |
|---|---|
| `obrik_aruco` | поле обрика с ArUco-метками (карта `markers_large.txt`) |
| `obrik_aruco_graffiti_wall` | поле ArUco со стеной для распылителя |
| `aruco` | штатный мир PX4 (карта `markers.txt`) |

Свою карту меток можно задать: `aruco_map_file:=/absolute/path/markers.txt`
(координаты и размеры меток должны совпадать с миром Gazebo).

---

## 6. Режимы навигации

Все команды — **внутри контейнера** (`docker exec -it sverk_sitl bash`). Флаг
показа (`vnc_gui` / `wslg_gpu_gui` / `host_x11_gui` / `headless` / `external_gazebo`) подставьте под
свой режим из раздела 4 — ниже для примера noVNC.

В актуальном SITL-launch `use_sim_time:=true` включён по умолчанию.
В примерах он также указан явно для существующих образов со старым launch
(например, без macOS-оверлея). Камера, ArUco, TF и VPE используют `/clock` Gazebo. Не отключайте его для ArUco-навигации: иначе VPE
считает все позы устаревшими и handoff не происходит. Сам факт существования
топика `/aruco/world_pose` не гарантирует подачу позы в PX4.

**Навигация по ArUco** (XY и yaw — от меток, высота — от нижнего дальномера):

```bash
ros2 launch launch_system full_system_sitl.launch.py use_sim_time:=true \
  vnc_gui:=true obrik_config:=graffiti gz_world:=obrik_aruco \
  enable_vio:=true allow_send_vio:=true
```

Взлетать после сообщения **`GPS-to-ArUco handoff complete`** в логе.

**Навигация по GPS** (XY от GPS, ArUco не подаётся в PX4):

```bash
ros2 launch launch_system full_system_sitl.launch.py use_sim_time:=true \
  vnc_gui:=true obrik_config:=graffiti gz_world:=obrik_aruco \
  enable_vio:=false allow_send_vio:=false
```

**Проверка ArUco без подачи в PX4** (смотрим позу, но EKF её не использует):

```bash
ros2 launch launch_system full_system_sitl.launch.py use_sim_time:=true \
  vnc_gui:=true obrik_config:=graffiti gz_world:=obrik_aruco \
  enable_vio:=true allow_send_vio:=false
```

---

## 7. Полёт: взлёт, посадка

Команды — **в новом терминале внутри контейнера** (симулятор оставьте
запущенным в первом). Если окружение не подхватилось:

```bash
source /opt/ros/humble/setup.bash && source /home/sverk/sverk_ws/install/setup.bash
```

**Взлёт на 1 м** (`auto_arm: true` — сам заармит):

```bash
ros2 service call /navigate offboard_interfaces/srv/Navigate \
  "{x: 0.0, y: 0.0, z: 1.0, yaw: 0.0, speed: 0.2, frame_id: 'map', auto_arm: true}"
```

**Полёт в точку** — меняйте `x/y/z/yaw`. **Посадка:**

```bash
ros2 service call /land std_srvs/srv/Trigger "{}"
```

**Распылитель (для `graffiti`)** — нажать / вернуть:

```bash
ros2 topic pub --once /servo_node/target_angle_deg std_msgs/msg/Float32 '{data: 156.52}'
ros2 topic pub --once /servo_node/target_angle_deg std_msgs/msg/Float32 '{data: 90.0}'
```

---

## 8. Что проверить

### EKF сошёлся (перед взлётом, ~2–3 мин)

```bash
ros2 topic echo /fmu/out/vehicle_local_position \
  --qos-reliability best_effort --qos-durability volatile
```
Ждём `xy_valid: true`, `z_valid: true`, `dead_reckoning: false`.
Для ArUco также дождитесь handoff, описанного ниже.

### Симуляция идёт в реальном времени (эталон ~1.0)

```bash
gz topic -e -t /world/obrik_aruco/stats -n 1 | grep real_time_factor
```
На слабом CPU в noVNC значение будет ниже 1.0 — это нормально, симуляция просто
идёт медленнее реального времени.

### ArUco детектируется

```bash
ros2 topic hz /aruco/world_pose          # есть частота — метки видны
ros2 topic echo --once /aruco/world_pose
ros2 topic echo --once /fmu/out/estimator_status_flags
```
После handoff в `estimator_status_flags` ожидаются `cs_ev_pos=true`,
`cs_ev_yaw=true`, `cs_rng_hgt=true`, `cs_gps=false`. Поле `dead_reckoning`
проверяйте в `vehicle_local_position`, а не в `estimator_status_flags`.

На хосте доступны регрессионные проверки:

```bash
# из корня репозитория; нужен работающий Docker и скачанный образ
python3 -m unittest discover -s simulation/tests -p 'test_*.py'
python3 simulation/tests/check_px4_ipc.py

# при запущенном симуляторе: готовность и полёт только в SITL
docker cp simulation/tests/check_sitl.py sverk_sitl:/tmp/check_sitl.py
docker exec -it sverk_sitl bash
source /opt/ros/humble/setup.bash
source /home/sverk/sverk_ws/install/setup.bash
python3 /tmp/check_sitl.py --flight
```

Без `--flight` проверяется только готовность: реальные данные VIO/положения,
ArUco fusion и доступность сервисов. Тест не поднимает симулятор самостоятельно.

### Веб-интерфейсы (в браузере на хосте)

| URL | Что |
|---|---|
| <http://localhost:6080/vnc.html> | рабочий стол Gazebo (только noVNC) |
| <http://localhost:8888> | rosboard — список топиков ROS |
| <http://localhost:8080> | web_video_server — видео с камеры |
| <http://localhost:5467> | VS Code в браузере (code-server) — только с аддоном `ide` |
| <http://localhost:8575> | butterfly — терминал в браузере — только с аддоном `ide` |

### Порты

| Порт | Назначение |
|---|---|
| 2222 | SSH в контейнер (`ssh sverk@localhost -p 2222`, пароль `sverk`) |
| 8888 / 9090 / 8080 | rosboard / ros_services_bridge / web_video_server |
| 6080 / 5900 | noVNC / VNC (только noVNC-режим) |
| 5467 / 8575 | code-server / веб-терминал (только с аддоном `ide`) |
| 8765 | MCP HTTP API (только с аддоном `mcp`) |
| 14550/udp | MAVLink → QGroundControl на хосте |
| 8086 | PID-ассистент (при `enable_pid_tuning:=true`) |

### QGroundControl (по желанию)

Если установлен QGroundControl — он сам подхватит поток MAVLink на UDP 14550 и
покажет дрон на карте, телеметрию, параметры.

---

## 9. Остановка и сброс

```bash
# внутри контейнера остановить симулятор: Ctrl+C
# остановить контейнер (том /home/sverk сохраняется — параметры, логи, сборки):
./sim.sh down novnc        # режим — тот же, что использовали при up
```

Полный сброс (удалить и данные, при следующем `up` — чистый `/home/sverk` из
образа) — добавьте `-v` к `down` вручную:

```bash
docker compose -f docker-compose.sim.yml -f docker-compose.sim.novnc.yml down -v
```

На Apple Silicon в команду полного сброса добавьте также
`-f docker-compose.sim.macos.yml` перед `down`; с аддонами добавьте их оверлеи.
Удаление тома стирает параметры, логи и пользовательские файлы в `/home/sverk`.
Сохраните нужные данные заранее.

Набор `-f` у `down` должен совпадать с тем, каким делали `up` (обёртки `sim.sh`/
`sim.ps1` подставляют его по имени режима автоматически).

---

## 10. Если что-то не так

- **Окно Gazebo не появилось в WSLg / Intel Arc** — переключитесь на noVNC:
  `./sim.sh down wslg-intel` → `./sim.sh up novnc`. noVNC устраняет необходимость проброса GPU; остальные проверки готовности остаются обязательными.
- **`docker exec ... sverk_sitl` → No such container** — контейнер не поднят,
  сделайте `./sim.sh up <режим>`.
- **Дрон не армится / не взлетает** — не сошёлся EKF: подождите 2–3 мин и
  проверьте `xy_valid/z_valid` (раздел 8). В ArUco-режиме дождитесь
  `GPS-to-ArUco handoff complete`.
- **Страница noVNC не загружается** — подождите 10–20 с после `up`, затем
  откройте :6080 снова. Если подключение есть, но после запуска сцены рабочий
  стол остаётся чёрным, выполните [перезапуск с исправленным GUI](#11-если-после-обновления-остался-чёрный-экран-novnc).
- **`ros2: command not found` внутри** — подгрузите окружение (раздел 7).
- **Порт занят (2222/8888/6080…)** — остановите прошлый контейнер (`./sim.sh
  down …`) или закройте занявшую порт программу.

- **Apple Silicon: `px4_daemon ... error connecting to socket`** — проверьте,
  что запускали `./sim.sh up novnc` из актуального репозитория. Повторный `up`
  соберёт библиотеку; в Compose должен присутствовать macOS-оверлей. HTTP 200
  от noVNC не означает готовности PX4.
- **`PX4 macOS compatibility library is missing`** — повторите `./sim.sh up novnc`
  или команду сборки из раздела macOS. Не задавайте `LD_PRELOAD` глобально.
- **`dropped stale world_pose` с огромным возрастом** — проверьте
  `use_sim_time:=true` и сообщения `/clock`; нужен актуальный launch-файл.
- **`Failed to load ... libOpticalFlowSystem.so`** — в проверенном образе
  библиотека отсутствует. Сценарий `base` с ArUco прошёл несмотря на это;
  работоспособность моделей с optical flow (`gigaobrik`) не подтверждена.
  Для них требуется включить совместимый плагин в новую сборку образа.
- **CLI ROS выдаёт `!rclpy.ok()` после перезапуска** — перезапустите CLI daemon
  внутри контейнера: `ros2 daemon stop`; следующий вызов запустит его снова.
  Для списка топиков можно использовать `ros2 topic list --no-daemon`.
- **После `pull` остался старый код** — том `/home/sverk` сохраняет workspace
  предыдущего образа. Сделайте резервную копию данных и проверьте новый образ
  с отдельным чистым томом. macOS-оверлей обновляет только смонтированный launch,
  а не весь сохранённый workspace.
- **После посадки пропал `/aruco/world_pose`** — проверьте кадр камеры:
  при смещении на земле метки могут быть обрезаны границей кадра. В проверке
  это приводило к потере VIO и `xy_valid` после посадки. Перед следующим взлётом
  заново проверьте готовность; если метки не видны, остановите и перезапустите
  сцену. Повторный автоматический взлёт после произвольного приземления
  этим исправлением не гарантируется.

Подробный журнал причин и оставшихся задач —
[fix_macos_list_sim.md](../../fix_macos_list_sim.md).

## 11. Если после обновления остался чёрный экран noVNC

В исправленном launch GUI запускается через `dbus-run-session`. Без своей
D-Bus-сессии Qt в проверенном контейнере зависал на accessibility-мосте ещё
до создания главного окна. При этом PX4, камера и ArUco продолжали работать.
Обновление вкладки не устраняет это зависание.

Если вы уже запустили старую команду, выполните следующие шаги.

**1. В терминале с журналом симулятора:** нажмите **Ctrl+C**.

**2. В этом терминале внутри контейнера:** выйдите на Mac:

```bash
exit
```

**3. На Mac:** перейдите в папку запуска:

```bash
cd ~/vierret-sverk/simulation/compose
```

**4. На Mac:** остановите прежний контейнер:

```bash
./sim.sh down novnc
```

**5. На Mac:** поднимите контейнер с актуальным launch:

```bash
./sim.sh up novnc
```

**6. На Mac:** войдите внутрь:

```bash
./sim.sh shell
```

**7. Внутри контейнера:** снова запустите сцену:

```bash
ros2 launch launch_system full_system_sitl.launch.py use_sim_time:=true vnc_gui:=true obrik_config:=base gz_world:=obrik_aruco
```

**8. В браузере:** откройте или переподключите
[noVNC](http://localhost:6080/vnc.html?autoconnect=1&resize=scale).

Проверка реального кадра (в отдельном терминале **на Mac**, из корня проекта):

```bash
cd ~/vierret-sverk
```

```bash
python3 simulation/tests/check_novnc.py --output /tmp/sverk-novnc.png
```

Команда обращается к локальному VNC :5900, сохраняет снимок и выявляет
полностью чёрный/однотонный viewport. `PASS` не заменяет визуальную проверку,
что на снимке именно поле симуляции. HTTP 200 от :6080 проверяет только веб-страницу.
