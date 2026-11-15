"""Run inside the Metal container: keep XRCE traffic local to the Linux VM."""
from pathlib import Path
import ipaddress
import socket

ORIGINAL = 'uxrce_dds_client start -t udp -h 127.0.0.1'
REPLACEMENT = 'uxrce_dds_client start -t udp -h "${PX4_UXRCE_DDS_HOST:-127.0.0.1}"'


def patch_startup(text):
    if REPLACEMENT in text:
        return text
    if text.count(ORIGINAL) != 1:
        raise RuntimeError('Unsupported PX4 rcS: expected exactly one loopback XRCE startup')
    return text.replace(ORIGINAL, REPLACEMENT, 1)


def main():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as route:
        route.connect(('host.docker.internal', 9))  # route lookup only; no datagram sent
        address = route.getsockname()[0]
    ip = ipaddress.IPv4Address(address)
    if ip.is_loopback or ip.is_unspecified:
        raise RuntimeError('Cannot determine a non-loopback Linux VM address for XRCE')
    startup = Path('/home/sverk/PX4-Autopilot/build/px4_sitl_default/etc/init.d-posix/rcS')
    text = startup.read_text()
    patched = patch_startup(text)
    if patched != text:
        startup.write_text(patched)
    Path('/tmp/sverk-xrce-agent.env').write_text(f'export PX4_UXRCE_DDS_HOST={address}\n')
    print(f'Metal XRCE: Linux VM agent address {address}', flush=True)


if __name__ == '__main__':
    main()
