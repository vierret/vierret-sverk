import importlib.util
from pathlib import Path
import socket
import struct
import threading
import unittest

PATH = Path(__file__).resolve().parents[1] / 'macos/discovery_bridge.py'
SPEC = importlib.util.spec_from_file_location('discovery_bridge', PATH)
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


class DiscoveryBridgeTests(unittest.TestCase):
    def test_tcp_fragmentation_preserves_datagram_boundaries(self):
        packets = [(10317, b'topic\0announcement'), (10318, b'service announcement')]
        encoded = b''.join(bridge.HEADER.pack(port, len(data)) + data for port, data in packets)
        frames = bridge.Frames()
        result = []
        for byte in encoded:
            result.extend(frames.feed(bytes([byte])))
        self.assertEqual(result, packets)
        self.assertEqual(frames.data, b'')

    def test_coalesced_packets_and_partial_tail(self):
        packet = bridge.HEADER.pack(10318, 3) + b'abc'
        frames = bridge.Frames()
        self.assertEqual(frames.feed(packet + packet[:4]), [(10318, b'abc')])
        self.assertEqual(frames.feed(packet[4:]), [(10318, b'abc')])

    def test_rejects_unrelated_ports_and_oversized_payloads(self):
        for header in (struct.pack('!HI', 80, 1), struct.pack('!HI', 10317, 0),
                       struct.pack('!HI', 10318, 2**32 - 1)):
            with self.subTest(header=header), self.assertRaises(ValueError):
                bridge.Frames().feed(header)

    def test_exchange_delivers_packet_and_stops_on_disconnect(self):
        class Local:
            receivers = ()

            def __init__(self):
                self.received = []

            def to_local(self, port, data):
                self.received.append((port, data))

        local = Local()
        left, right = socket.socketpair()
        errors = []

        def receive():
            try:
                with left:
                    bridge.exchange(left, local)
            except Exception as error:
                errors.append(error)

        thread = threading.Thread(target=receive)
        thread.start()
        with right:
            right.sendall(bridge.MAGIC)
            self.assertEqual(right.recv(len(bridge.MAGIC)), bridge.MAGIC)
            right.sendall(bridge.HEADER.pack(10318, 5) + b'hello')
        thread.join(timeout=3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(local.received, [(10318, b'hello')])


if __name__ == '__main__':
    unittest.main()
