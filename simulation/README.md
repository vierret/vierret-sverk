# SVERK SITL — симулятор дрона

Симулятор дрона SVERK (PX4 + Gazebo Harmonic + ROS 2) в готовом Docker-образе:
скачиваете и запускаете без сборки ROS/PX4. На Apple Silicon обёртка дополнительно
компилирует небольшую библиотеку совместимости внутри контейнера. Внутри — тот же полётный
стек, что на реальном дроне: навигация по ArUco, дальномеры, камера,
взлёт/посадка по сервису.

## Быстрый старт на Mac

Полная последовательность с проверками и первым полётом — в
**[пошаговой инструкции](docs/guide.md)**. Команды ниже вводятся по одной.

**1. Терминал на Mac:** перейдите в папку проекта (если он лежит в другом месте,
укажите свой путь):

```bash
cd ~/vierret-sverk/simulation/compose
```

**2. В этом же терминале на Mac:** скачайте образ при первой установке:

```bash
./sim.sh pull
```

**3. На Mac:** поднимите контейнер. `.env` создаётся автоматически:

```bash
./sim.sh up novnc
```

**4. В браузере на Mac:** откройте
[noVNC](http://localhost:6080/vnc.html?autoconnect=1&resize=scale).
Нажмите Connect, если требуется. До запуска сцены рабочий стол может быть пустым.

**5. В том же терминале на Mac:** войдите в контейнер:

```bash
./sim.sh shell
```

Приглашение станет `sverk@…:~$`.

**6. Теперь внутри контейнера:** запустите сцену одной строкой:

```bash
ros2 launch launch_system full_system_sitl.launch.py use_sim_time:=true vnc_gui:=true obrik_config:=base gz_world:=obrik_aruco
```

Оставьте терминал работающим. В noVNC должно появиться окно Gazebo с полем.
Разверните окно двойным щелчком по его заголовку; приближайте поле колесом мыши.
Для ArUco-полёта дождитесь `GPS-to-ArUco handoff complete` и выполните проверку
готовности из [шага 3.5 руководства](docs/guide.md).

На **Apple Silicon** `sim.sh` автоматически подключает
`docker-compose.sim.macos.yml` и подготавливает обход `poll/EINTR` в PX4.
GUI запускается в отдельной D-Bus-сессии, чтобы Qt не зависал до появления окна.
Для Mac нужна полная копия репозитория. Образ остаётся `linux/amd64`;
рендер выполняется на CPU.

Полное руководство (режимы отображения, модели и миры, навигация, полёт,
проверки, аддоны Web-IDE и MCP, траблшутинг) — в
**[docs/guide.md](docs/guide.md)**. На Windows используйте `sim.ps1` в PowerShell;
порядок входа в контейнер и запуска сцены описан там же.

## Структура

```
simulation/
├── compose/                          # docker compose + скрипты запуска
│   ├── docker-compose.sim.yml        # база (headless)
│   ├── docker-compose.sim.novnc.yml  # noVNC — картинка в браузере, CPU-рендер
│   ├── docker-compose.sim.macos.yml  # совместимость PX4 на Apple Silicon
│   ├── docker-compose.sim.wslg.yml + .wslg.nvidia.yml / .wslg.intel.yml   # Windows GPU-окно
│   ├── docker-compose.sim.linux-host.yml   # нативный Linux X11
│   ├── docker-compose.sim.ide.yml    # Web-IDE (VS Code + терминал в браузере)
│   ├── docker-compose.sim.mcp.yml    # MCP HTTP-сервер :8765
│   ├── mcp_policy.yaml                # права MCP
│   ├── .env.example                  # теги образов
│   ├── sim.ps1                        # обёртка для Windows
│   └── sim.sh                         # обёртка для Linux/WSL/macOS
├── compat/                           # обход poll/EINTR в опубликованном PX4
├── tests/                            # проверки обёртки, IPC и полёта
└── docs/
    └── guide.md                      # руководство пользователя
```

## Режимы одним взглядом

| Режим | Команда (из `compose/`) | Картинка |
|---|---|---|
| noVNC (рекомендуется) | `./sim.sh up novnc` | браузер :6080 |
| WSLg + NVIDIA | `./sim.sh up wslg-nvidia` | окно на рабочем столе |
| WSLg + Intel Arc | `./sim.sh up wslg-intel` | окно (или noVNC) |
| Linux X11 | `./sim.sh up linux-host` | окно на рабочем столе |
| headless | `./sim.sh up headless` | нет окна |

Аддоны (добавляются к режиму): `./sim.sh up novnc mcp`, `./sim.sh up headless ide+mcp`.

На Apple Silicon основной проверенный режим — noVNC с моделью `base` и миром
`obrik_aruco`. WSLg и Linux X11 предназначены для соответствующих ОС.
