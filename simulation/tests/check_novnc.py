#!/usr/bin/env python3
"""Read the actual noVNC desktop over RFB; fail on a black/empty viewport."""
import argparse
from collections import Counter
from pathlib import Path
import socket
import struct
import zlib


def read_exact(stream, size):
    data = bytearray()
    while len(data) < size:
        chunk = stream.recv(size - len(data))
        if not chunk:
            raise RuntimeError('VNC connection closed before a complete frame')
        data.extend(chunk)
    return bytes(data)


def screenshot(host, port):
    with socket.create_connection((host, port), timeout=15) as stream:
        version = read_exact(stream, 12)
        if version != b'RFB 003.008\n':
            raise RuntimeError(f'Unsupported RFB protocol: {version!r}')
        stream.sendall(version)
        count = read_exact(stream, 1)[0]
        security = read_exact(stream, count)
        if 1 not in security:
            raise RuntimeError('Local no-password VNC is required')
        stream.sendall(b'\x01')
        if struct.unpack('>I', read_exact(stream, 4))[0] != 0:
            raise RuntimeError('VNC security negotiation failed')
        stream.sendall(b'\x01')  # shared connection; do not disconnect the browser
        header = read_exact(stream, 24)
        width, height = struct.unpack('>HH', header[:4])
        read_exact(stream, struct.unpack('>I', header[20:24])[0])
        pixel_format = struct.pack('>BBBBHHHBBBxxx', 32, 24, 0, 1, 255, 255, 255, 16, 8, 0)
        stream.sendall(b'\x00\x00\x00\x00' + pixel_format)
        stream.sendall(struct.pack('>BBHi', 2, 0, 1, 0))  # raw encoding
        stream.sendall(struct.pack('>BBHHHH', 3, 0, 0, 0, width, height))
        pixels = bytearray(width * height * 4)
        while True:
            kind = read_exact(stream, 1)[0]
            if kind == 0:
                _, rectangles = struct.unpack('>BH', read_exact(stream, 3))
                for _ in range(rectangles):
                    x, y, w, h, encoding = struct.unpack('>HHHHi', read_exact(stream, 12))
                    if encoding != 0:
                        raise RuntimeError(f'Unexpected VNC encoding: {encoding}')
                    raw = read_exact(stream, w * h * 4)
                    for row in range(h):
                        start = ((y + row) * width + x) * 4
                        pixels[start:start + w * 4] = raw[row * w * 4:(row + 1) * w * 4]
                return width, height, pixels
            if kind == 2:  # bell
                continue
            if kind == 3:  # clipboard
                clipboard = read_exact(stream, 7)
                read_exact(stream, struct.unpack('>I', clipboard[3:])[0])
                continue
            raise RuntimeError(f'Unexpected VNC message: {kind}')


def save_png(path, width, height, pixels):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            offset = (y * width + x) * 4
            rows.extend(pixels[offset:offset + 3][::-1])
    png = b'\x89PNG\r\n\x1a\n'
    png += chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(bytes(rows))) + chunk(b'IEND', b'')
    path.write_bytes(png)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5900)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    width, height, pixels = screenshot(args.host, args.port)
    if args.output:
        save_png(args.output, width, height, pixels)
    colors = Counter()
    for y in range(height // 10, height * 9 // 10, 4):
        for x in range(width // 10, width * 9 // 10, 4):
            offset = (y * width + x) * 4
            colors[tuple(pixels[offset:offset + 3])] += 1
    bright = sum(count for color, count in colors.items() if max(color) > 24) / sum(colors.values())
    print(f'VNC desktop: {width}x{height}; viewport colors={len(colors)}, nonblack={bright:.1%}')
    if len(colors) < 64 or bright < 0.1:
        raise SystemExit('FAIL: VNC viewport is black/empty; HTTP 200 alone is insufficient')
    print('PASS: VNC viewport contains a rendered image (inspect PNG to confirm the scene)')


if __name__ == '__main__':
    main()
