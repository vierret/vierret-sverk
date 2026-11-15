#!/usr/bin/env python3
"""Bridge local Gazebo discovery multicast across Docker Desktop using TCP.

Only discovery is forwarded; Gazebo's advertised TCP endpoints still require
Desktop host networking. Run one listen process on macOS and one connect
process inside Linux. Nothing is bound to a public host interface.
"""
import argparse
import collections
import hashlib
import os
import select
import socket
import struct
import time

MAGIC = b'SVERK-GZ-DISC-1\n'
HEADER = struct.Struct('!HI')
PORTS = (10317, 10318)
GROUP = '239.255.0.7'
MAX_DATAGRAM = 65507


class Frames:
    def __init__(self):
        self.data = bytearray()

    def feed(self, data):
        self.data.extend(data)
        result = []
        while len(self.data) >= HEADER.size:
            port, size = HEADER.unpack_from(self.data)
            if port not in PORTS or not 0 < size <= MAX_DATAGRAM:
                raise ValueError('Invalid discovery bridge frame')
            if len(self.data) < HEADER.size + size:
                break
            result.append((port, bytes(self.data[HEADER.size:HEADER.size+size])))
            del self.data[:HEADER.size+size]
        return result


class LocalDiscovery:
    def __init__(self):
        self.receivers = {}
        self.senders = {}
        self.local_ports = dict(zip(PORTS, (
            int(os.environ.get('GZ_DISCOVERY_MSG_PORT', '10317')),
            int(os.environ.get('GZ_DISCOVERY_SRV_PORT', '10318')),
        )))
        self.recent = collections.OrderedDict()
        for port in PORTS:
            receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            receiver.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, 'SO_REUSEPORT'):
                receiver.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            receiver.bind(('', self.local_ports[port]))
            receiver.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                                socket.inet_aton(GROUP) + socket.inet_aton('127.0.0.1'))
            self.receivers[receiver] = port
            sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sender.bind(('127.0.0.1', 0))
            sender.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton('127.0.0.1'))
            sender.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 0)
            sender.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
            self.senders[port] = sender

    def to_local(self, port, data):
        fingerprint = (port, hashlib.blake2s(data, digest_size=16).digest())
        self.recent[fingerprint] = time.monotonic()
        self.recent.move_to_end(fingerprint)
        while len(self.recent) > 4096:
            self.recent.popitem(last=False)
        self.senders[port].sendto(data, (GROUP, self.local_ports[port]))

    def from_local(self, receiver):
        data, peer = receiver.recvfrom(MAX_DATAGRAM)
        port = self.receivers[receiver]
        # Do not send a packet straight back to the peer that forwarded it.
        if peer == self.senders[port].getsockname():
            return None
        fingerprint = (port, hashlib.blake2s(data, digest_size=16).digest())
        if time.monotonic() - self.recent.get(fingerprint, -10) < 0.25:
            return None
        if not data:
            return None
        return HEADER.pack(port, len(data)) + data

    def close(self):
        for sock in (*self.receivers, *self.senders.values()):
            sock.close()


def exchange(stream, local):
    stream.settimeout(3)
    stream.sendall(MAGIC)
    handshake = b''
    while len(handshake) < len(MAGIC):
        chunk = stream.recv(len(MAGIC) - len(handshake))
        if not chunk:
            raise ConnectionError('Peer closed during handshake')
        handshake += chunk
    if handshake != MAGIC:
        raise ValueError('Peer is not a compatible Gazebo discovery bridge')
    stream.settimeout(2)
    print('Gazebo discovery bridge connected', flush=True)
    frames = Frames()
    while True:
        ready, _, _ = select.select([stream, *local.receivers], [], [], 1)
        for sock in ready:
            if sock is stream:
                data = stream.recv(65536)
                if not data:
                    return
                for port, payload in frames.feed(data):
                    local.to_local(port, payload)
            else:
                data = local.from_local(sock)
                if data:
                    stream.sendall(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('listen', 'connect'))
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=int(os.environ.get('SVERK_METAL_BRIDGE_PORT', '19090')))
    args = parser.parse_args()
    local = LocalDiscovery()
    listener = None
    try:
        if args.mode == 'listen':
            if args.host != '127.0.0.1':
                parser.error('The host discovery bridge must listen on loopback')
            listener = socket.socket()
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((args.host, args.port))
            listener.listen(1)
            listener.settimeout(1)
            print(f'Gazebo discovery bridge listening on {args.host}:{args.port}', flush=True)
        while True:
            try:
                if listener:
                    try:
                        stream, _ = listener.accept()
                    except socket.timeout:
                        continue
                else:
                    stream = socket.create_connection((args.host, args.port), timeout=3)
                with stream:
                    exchange(stream, local)
            except (OSError, ValueError) as error:
                print(f'Gazebo discovery bridge reconnecting: {error}', flush=True)
                time.sleep(1)
    finally:
        if listener:
            listener.close()
        local.close()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
