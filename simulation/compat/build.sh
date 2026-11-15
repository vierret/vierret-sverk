#!/usr/bin/env bash
# Compile inside the container: never load a macOS or wrong-architecture library.
set -euo pipefail
compat_dir="$(cd "$(dirname "$0")" && pwd)"
library=/tmp/sverk-px4-poll-eintr.so
if ! command -v cc >/dev/null 2>&1; then
  echo 'SITL macOS: нужен C-компилятор в образе (cc/gcc). Используйте поддерживаемый образ.' >&2
  exit 1
fi
cc -shared -fPIC -O2 -Wall -Wextra -Werror \
  "$compat_dir/px4_poll_eintr.c" -ldl -o "${library}.new"
mv "${library}.new" "$library"
echo 'SITL macOS: совместимость PX4 poll/EINTR подготовлена.'
