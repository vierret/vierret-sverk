#!/usr/bin/env bash
# SVERK SITL — обёртка над docker compose (Linux / WSL / macOS).
# Запускать из папки compose/.
#
#   ./sim.sh up   novnc          # поднять noVNC-режим (рекомендуется)
#   ./sim.sh up   wslg-nvidia    # WSLg + NVIDIA (только из Ubuntu-24.04!)
#   ./sim.sh up   wslg-intel     # WSLg + Intel Arc
#   ./sim.sh up   linux-host     # нативный Linux X11 (сначала: xhost +local:docker)
#   ./sim.sh up   headless       # без картинки (только физика)
#   ./sim.sh up   headless ide   # + Web-IDE (VS Code :5467 / терминал :8575)
#                                #   аддон ide сочетается со всеми режимами, КРОМЕ novnc
#   ./sim.sh up   novnc   mcp    # + MCP-сервер :8765 (сочетается с любым режимом)
#   ./sim.sh up   headless ide+mcp   # несколько аддонов через +
#   ./sim.sh shell               # войти в контейнер (docker exec bash)
#   ./sim.sh down headless ide   # остановить (режим и аддон — те же, что при up)
#   ./sim.sh pull                # docker pull образов
#   ./sim.sh logs
set -euo pipefail
cd "$(dirname "$0")"

CMD="${1:-}"
MODE="${2:-novnc}"
ADDON="${3:-}"

fail() { echo "$*" >&2; exit 1; }

[ "$#" -le 3 ] || fail "Лишние аргументы. Формат: $0 <up|down|pull|logs|shell> [режим] [ide+mcp]"
case "$CMD" in up|down|pull|logs|shell) ;; *) fail "Неизвестная команда '$CMD'. Доступно: up | down | pull | logs | shell" ;; esac

# shell does not need Compose, .env or a particular display mode.
if [ "$CMD" = shell ]; then
  exec docker exec -it sverk_sitl bash
fi

compose_args=(-f docker-compose.sim.yml)
case "$MODE" in
  novnc) compose_args+=(-f docker-compose.sim.novnc.yml) ;;
  wslg-nvidia) compose_args+=(-f docker-compose.sim.wslg.yml -f docker-compose.sim.wslg.nvidia.yml) ;;
  wslg-intel) compose_args+=(-f docker-compose.sim.wslg.yml -f docker-compose.sim.wslg.intel.yml) ;;
  linux-host) compose_args+=(-f docker-compose.sim.linux-host.yml) ;;
  headless) ;;
  *) fail "Неизвестный режим '$MODE'. Доступно: novnc | wslg-nvidia | wslg-intel | linux-host | headless" ;;
esac

macos_compat="${SIM_MACOS_COMPAT:-auto}"
if [ "$macos_compat" = auto ]; then
  macos_compat=0
  if [ "$(uname -s)" = Darwin ] && [ "$(uname -m)" = arm64 ]; then
    macos_compat=1
  fi
fi
case "$macos_compat" in
  1)
    case "$MODE" in novnc|headless) ;; *) fail "Apple Silicon: используйте novnc или headless." ;; esac
    compose_args+=(-f docker-compose.sim.macos.yml) ;;
  0) ;;
  *) fail "SIM_MACOS_COMPAT должен быть auto, 0 или 1." ;;
esac

# Parse add-ons without unquoted command substitution (Bash 3.2 compatible).
case "$ADDON" in +*|*+|*++*) fail "Некорректный список аддонов '$ADDON'. Используйте ide, mcp или ide+mcp." ;; esac
addon_args=("")
if [ -n "$ADDON" ]; then
  IFS='+' read -r -a addon_args <<< "$ADDON"
fi
for addon in "${addon_args[@]}"; do
  case "$addon" in
    ide)
      [ "$MODE" != novnc ] || fail "Аддон ide несовместим с novnc. Терминал есть в рабочем столе :6080."
      compose_args+=(-f docker-compose.sim.ide.yml) ;;
    mcp) compose_args+=(-f docker-compose.sim.mcp.yml) ;;
    "") ;;
    *) fail "Неизвестный аддон '$addon'. Доступно: ide | mcp (или ide+mcp)" ;;
  esac
done

if [ ! -f .env ]; then
  [ -f .env.example ] || fail "Нет .env.example. Восстановите файл из репозитория."
  echo "-> .env не найден, копирую из .env.example"
  cp .env.example .env
fi

case "$CMD" in
  up)
    docker compose "${compose_args[@]}" up -d
    if [ "$macos_compat" = 1 ]; then
      docker compose "${compose_args[@]}" exec -T sitl bash /opt/sverk/sitl-compat/build.sh
    fi
    [ "$MODE" != novnc ] || echo "noVNC: http://localhost:6080/vnc.html"
    case "$ADDON" in *ide*) echo "Web-IDE: http://localhost:5467  |  терминал: http://localhost:8575" ;; esac
    case "$ADDON" in *mcp*) echo "MCP: http://localhost:8765/healthz" ;; esac ;;
  down) docker compose "${compose_args[@]}" down ;;
  pull) docker compose "${compose_args[@]}" pull ;;
  logs) docker compose "${compose_args[@]}" logs -f ;;
esac
