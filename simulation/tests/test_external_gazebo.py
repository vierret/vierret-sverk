"""Exercise the actual launch command builder without importing the ROS runtime."""
import ast
import os
from pathlib import Path
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]


def command_builder():
    path = ROOT / 'main_package/launch_system/launch/full_system_sitl.launch.py'
    tree = ast.parse(path.read_text())
    functions = {'_make_px4_launch', '_resolve_obrik_model', '_is_obrik_model', '_llvmpipe_threads'}
    nodes = [node for node in tree.body if
             isinstance(node, ast.FunctionDef) and node.name in functions
             or isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and
                 t.id in ('OBRIK_CONFIG_MODELS', 'DEFAULT_X500_MODEL') for t in node.targets)]

    class Config:
        def __init__(self, name):
            self.name = name

        def perform(self, context):
            return context[self.name]

    namespace = dict(os=os, LaunchConfiguration=Config, ExecuteProcess=lambda **kwargs: kwargs)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace['_make_px4_launch']


class ExternalGazeboTests(unittest.TestCase):
    def setUp(self):
        self.context = dict(external_gazebo='true', headless='false', wslg_gui='false',
                            wslg_gpu_gui='false', host_x11_gui='false', vnc_gui='false',
                            obrik_config='base', gz_world='obrik_aruco', enable_vio='true',
                            allow_send_vio='true')

    def test_external_server_is_not_started_or_forced_to_cpu(self):
        with patch.dict(os.environ, {}, clear=True):
            process = command_builder()(self.context, '/fixture/PX4')[0]
        command = process['cmd'][2]
        self.assertIn('PX4_GZ_STANDALONE=1', command)
        self.assertIn('PX4_SIM_MODEL=gz_x500_obrik_base', command)
        self.assertNotIn('gz sim', command)
        self.assertNotIn('LIBGL_ALWAYS_SOFTWARE', process['additional_env'])
        self.assertNotIn('GALLIUM_DRIVER', process['additional_env'])

    def test_external_server_rejects_local_display_modes(self):
        for flag in ('headless', 'vnc_gui', 'wslg_gui', 'wslg_gpu_gui', 'host_x11_gui'):
            with self.subTest(flag=flag), patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ValueError, 'external_gazebo'):
                    command_builder()(dict(self.context, **{flag: 'true'}), '/fixture/PX4')


if __name__ == '__main__':
    unittest.main()
