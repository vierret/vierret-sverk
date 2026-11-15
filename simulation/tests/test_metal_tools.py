"""Metal launcher behavior, independent of native frameworks on CI."""
import base64
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


PATH = Path(__file__).resolve().parents[1] / 'macos/metal_sim.py'
SPEC = importlib.util.spec_from_file_location('metal_sim', PATH)
metal = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(metal)


class MetalToolsTests(unittest.TestCase):
    def test_xrce_startup_patch_keeps_default_and_is_idempotent(self):
        spec = importlib.util.spec_from_file_location('prepare_xrce', PATH.parent / 'prepare_xrce.py')
        prepare = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(prepare)
        original = '#!/bin/sh\n' + prepare.ORIGINAL + ' -p $uxrce_dds_port\n'
        patched = prepare.patch_startup(original)
        self.assertIn('${PX4_UXRCE_DDS_HOST:-127.0.0.1}', patched)
        self.assertIn('-p $uxrce_dds_port', patched)
        self.assertEqual(prepare.patch_startup(patched), patched)
        with self.assertRaises(RuntimeError):
            prepare.patch_startup('unexpected startup')

    def test_native_environment_drops_linux_renderer_overrides(self):
        with patch.dict(os.environ, {'GALLIUM_DRIVER': 'llvmpipe', 'LIBGL_ALWAYS_SOFTWARE': '1',
                                     'DISPLAY': ':99', 'QT_QPA_PLATFORM': 'xcb',
                                     'LD_PRELOAD': '/linux.so', 'SVERK_METAL_PARTITION': 'test'}, clear=True):
            env = metal.native_environment()
            self.assertEqual(env['GZ_PARTITION'], 'test')
            self.assertEqual(env['GZ_IP'], '127.0.0.1')
            for key in ('GALLIUM_DRIVER', 'LIBGL_ALWAYS_SOFTWARE', 'DISPLAY', 'QT_QPA_PLATFORM', 'LD_PRELOAD'):
                self.assertNotIn(key, env)
            self.assertEqual(os.environ['GALLIUM_DRIVER'], 'llvmpipe')

    def test_server_and_gui_request_metal_in_separate_processes(self):
        with tempfile.TemporaryDirectory() as tmp:
            assets = Path(tmp)
            (assets / 'worlds').mkdir()
            (assets / 'worlds/obrik_aruco.sdf').touch()
            with patch.object(metal, 'ASSETS', assets), patch.object(metal.shutil, 'which', return_value='/native/gz'):
                server = metal.gazebo_command('server')
                gui = metal.gazebo_command('gui')
        self.assertIn('-s', server)
        self.assertNotIn('-g', server)
        self.assertIn('--render-engine-server-api-backend', server)
        self.assertEqual(server[-1], 'metal')
        self.assertIn('-g', gui)
        self.assertNotIn('-s', gui)
        self.assertEqual(gui[-1], 'metal')

    def test_camera_check_rejects_empty_or_truncated_images(self):
        blank = dict(width=16, height=16, step=48, pixelFormatType='RGB_INT8',
                     data=base64.b64encode(bytes(16*16*3)).decode())
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'frame.png'
            with self.assertRaisesRegex(RuntimeError, 'uniform'):
                metal.save_camera(blank, target)
            with self.assertRaisesRegex(RuntimeError, 'payload'):
                metal.save_camera(dict(blank, data=''), target)
            self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
