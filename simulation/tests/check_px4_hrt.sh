#!/usr/bin/env bash
# Run INSIDE a dedicated SITL test container. The old HRT may hang PX4.
set -euo pipefail
test_dir="$(cd "$(dirname "$0")" && pwd)"
px4_bin=/home/sverk/PX4-Autopilot/build/px4_sitl_default/bin
c++ -std=c++14 -shared -fPIC -pthread "$test_dir/px4_hrt_rearm.cpp" -o /tmp/px4_hrt_rearm.px4
: > /tmp/px4-hrt-rearm-result
if ! timeout 10 "$px4_bin/px4-dyn" /tmp/px4_hrt_rearm.px4; then
    echo 'FAIL: HRT re-arm hung or the PX4 module failed'
    exit 1
fi
cat /tmp/px4-hrt-rearm-result
grep -q '^PASS:' /tmp/px4-hrt-rearm-result
