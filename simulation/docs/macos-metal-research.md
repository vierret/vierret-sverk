# Apple Silicon acceleration: feasibility notes

Research date: 2026-11-15. Primary documentation and upstream release-branch source were inspected; no native Gazebo, cross-host Transport, or GPU sensor workload was executed as part of this note. Upstream branch links can change and do not establish the versions installed locally.

Subsequent implementation and measured local results are recorded separately in [macos-metal.md](macos-metal.md).

## Recommendation

For Apple GPU rendering, prototype **native arm64 Gazebo Harmonic server and GUI**, retaining PX4 / ROS applications in Docker where practical. Moving only the GUI to macOS can improve the interactive viewport, but does not accelerate cameras used by ArUco navigation: the server owns rendering sensors. Treat native GUI + Docker server as a separate, limited viewport experiment. These recommendations follow the process boundaries and backend support described below; performance and project compatibility remain unmeasured.

Do not describe this as an MPS switch for the existing amd64 image. Apple defines Metal as the GPU graphics/compute API and Metal Performance Shaders as an optimized shader library integrated into Metal applications. Gazebo's implementation selects an OGRE **Metal render system**, not an MPS execution device. [Apple Metal](https://developer.apple.com/documentation/metal), [Apple MPS](https://developer.apple.com/documentation/metalperformanceshaders), [Harmonic rendering source](https://github.com/gazebosim/gz-rendering/blob/gz-rendering8/ogre2/src/Ogre2RenderEngine.cc)

**Support horizon:** the Gazebo PMC announced on 2026-11-07 that native macOS support for Harmonic and Fortress ends **2027-01-10**, when Homebrew disables their freeimage dependency; Qt5 is another retiring dependency. The native Harmonic experiment is therefore a short-term option, and a maintained long-term native deployment needs a separately validated newer Gazebo release. [Official support announcement](https://discourse.openrobotics.org/t/early-end-of-support-of-gazebo-harmonic-fortress-on-macos/59605)

## Native macOS support exists

- Harmonic uses gz-rendering 8.x; macOS and arm platforms are supported on a best-effort basis. [Harmonic installation/support](https://gazebosim.org/docs/harmonic/install/)
- The Harmonic macOS installation page offers `brew tap osrf/simulation`, `brew trust osrf/simulation`, and `brew install gz-harmonic`. It currently describes Apple Silicon arm64 bottles for macOS Sequoia; other macOS versions may build from source. This does not prove bottle availability for this machine's OS or exact requested package revision. [macOS installation](https://gazebosim.org/docs/harmonic/install_osx/)
- gz-rendering8 loads `RenderSystem_Metal`, selects `Metal Rendering Subsystem`, and supplies Metal shader resources when the Metal backend is selected. gz-gui8's MinimalScene also implements a Metal render interface and platform-specific Metal selection. This establishes implementation support, not successful rendering of this project's assets. [rendering source](https://github.com/gazebosim/gz-rendering/blob/gz-rendering8/ogre2/src/Ogre2RenderEngine.cc), [GUI source](https://github.com/gazebosim/gz-gui/blob/gz-gui8/src/plugins/minimal_scene/MinimalScene.cc)
- Official macOS guidance launches server and GUI separately (`gz sim -s …`, `gz sim -g`) and warns that some GUI plugins can crash. A successful minimal scene is insufficient to claim the complete project GUI is stable. [Harmonic getting started](https://gazebosim.org/docs/harmonic/)

For macOS 26.6.2 specifically, Homebrew's current requirements cover Apple Silicon and macOS 15 or newer, with Xcode / Command Line Tools required for source builds. Use the native `/opt/homebrew` prefix. This establishes Homebrew eligibility, not tested Gazebo compatibility or OS-specific bottle availability. Query `brew info osrf/simulation/gz-harmonic` and its dependency formulae before installing; do not force a Sequoia bottle onto Tahoe. [Homebrew requirements](https://docs.brew.sh/Installation), [Harmonic formula](https://github.com/osrf/homebrew-simulation/blob/master/Formula/gz-harmonic.rb)

### Exact native smoke-test commands

Harmonic's own command parser documents the per-process backend flags below. Execute each line in a separate native terminal after installation; these are proposed validation commands, not tested results. [Harmonic CLI source](https://github.com/gazebosim/gz-sim/blob/gz-sim8/src/cmd/cmdsim.rb.in)

```sh
GZ_PARTITION=sverk-metal-check gz sim -v 4 -s shapes.sdf --render-engine-server ogre2 --render-engine-server-api-backend metal
```

```sh
GZ_PARTITION=sverk-metal-check gz sim -v 4 -g --render-engine-gui ogre2 --render-engine-gui-api-backend metal
```

The native GUI's `Application` selects `QSGRendererInterface::MetalRhi` through `QQuickWindow::setSceneGraphBackend`, and logs `Qt using Metal graphics interface`; external `QT_QUICK_BACKEND` or `QSG_RHI_BACKEND` overrides are not required by this upstream path. Confirm that log and OGRE Metal selection in the actual installed build. [Qt integration source](https://github.com/gazebosim/gz-gui/blob/gz-gui8/src/Application.cc)

## Docker is not a demonstrated OGRE Metal path

Docker Desktop runs its Engine in a Linux VM. Its documented `--gpus` Linux-container passthrough applies to Windows / WSL2, with other acceleration mechanisms such as Model Runner explicitly distinguished. This is not documentation for exposing Apple's native Metal framework to an ordinary Linux Gazebo process. [Desktop architecture/networking](https://docs.docker.com/desktop/features/networking/), [GPU documentation](https://docs.docker.com/desktop/features/gpu/)

The current official GPU page and Desktop release notes inspected here did not document a supported macOS WebGPU-to-OGRE path. A `docker.com/gpu=webgpu` CDI entry, if present locally, is not proof that Gazebo can use it. Harmonic's OGRE backend source selects OpenGL, Vulkan or Metal; it has no WebGPU selection. Therefore enabling a WebGPU device cannot presently be recommended as a drop-in solution for this image. A newer documented bridge would need separate validation, including a compatible OGRE backend or API translation layer. This is a bounded finding, not a claim that all container GPU mechanisms are impossible. [release notes](https://docs.docker.com/desktop/release-notes/), [rendering source](https://github.com/gazebosim/gz-rendering/blob/gz-rendering8/ogre2/src/Ogre2RenderEngine.cc)

## Sensor and network boundaries matter

The gz-sim8 Sensors system creates its own render utility, enables sensor creation, and defaults its API backend to `metal` on Apple builds. Thus an inference from the source is that native server execution is needed to move these rendering sensors onto that backend; a remote native GUI does not migrate the Docker server's sensor work. Verify actual camera/depth/GPU lidar formats, rates and image content independently. [Sensors source](https://github.com/gazebosim/gz-sim/blob/gz-sim8/src/systems/sensors/Sensors.cc)

Gazebo Transport's relay supports unicast discovery when multicast cannot cross networks, but **both nodes' advertised data endpoints must remain reachable in both directions**. The official Docker relay example uses Linux-style reachable bridge addresses; it is not evidence that macOS Desktop NAT supports the same recipe. `GZ_RELAY` alone does not solve inaccessible data endpoints. Use a common explicit `GZ_PARTITION`; select `GZ_IP` only after establishing the correct reachable addresses. [Transport 13 relay tutorial](https://gazebosim.org/api/transport/13/relay.html), [Transport environment variables](https://gazebosim.org/api/transport/13/envvars.html)

Docker Desktop host networking is an opt-in feature from 4.34 onward, supports TCP/UDP at layer 4, and does not give containers direct access to host interfaces. It is a candidate for experiments, not a guarantee of multicast discovery or correct Gazebo endpoint advertisement. [Host network documentation](https://docs.docker.com/engine/network/drivers/host/)

Its documented UI path is **Settings → Resources → Network → Enable host networking → Apply and restart**, then `--network host` (Compose `network_mode: host`) for the container. Published port mappings are ignored in this mode. Enhanced Container Isolation is incompatible with this feature. Start a native GUI with the same partition as the Docker server using the GUI command above; keep the existing Linux sensor backend and software rendering settings on the Docker server. Do not pass `metal` to that Linux process. Validate the actual topic and service round trips before presenting this as a working mode. [Host networking setup and limitations](https://docs.docker.com/engine/network/drivers/host/)

## Acceptance gates for a prototype

1. Record macOS, CPU architecture, Homebrew package versions and OGRE logs. Run a native stock world with server and GUI in separate terminals. Confirm the logged render system is Metal rather than inferring it from the host hardware.
2. Run the project's actual world and camera sensors natively. Check image content, camera rate, real-time factor, CPU usage and Apple GPU activity against the same workload in noVNC. Validate custom plugins/assets and native library compatibility.
3. Before integrating flight, prove Docker-to-host and host-to-Docker Gazebo topics **and services**, including sustained image delivery. Discovery listing alone does not meet the Transport reachability requirement.
4. Integrate PX4's Gazebo bridge and ROS consumers with matched Gazebo message/Transport major versions and explicit partitions. Validate clock, spawn/control services, camera delivery and ArUco flight behavior. Determine whether transport networking or additional native plugins must be changed; no end-to-end compatibility is asserted here.
5. Keep the existing documented noVNC route available until these gates pass. Compare measurements before claiming simulation speedup; rendering support alone says nothing about PX4 or physics acceleration.
