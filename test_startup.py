"""Exercise the real registry in an isolated test key, never the Windows Run key."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid
import winreg

import startup


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.key = r'Software\GHubIndicatorTests_' + uuid.uuid4().hex

    def tearDown(self):
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, self.key)
        except FileNotFoundError:
            pass

    def test_enable_disable_and_preserve_unrelated_values(self):
        self.assertFalse(startup.is_enabled(self.key))
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, self.key) as key:
            winreg.SetValueEx(key, 'UnrelatedApp', 0, winreg.REG_SZ, 'unchanged')
        command = r'"C:\My Apps\GHubIndicator.exe" --port 9010'
        startup.set_enabled(True, command, self.key)
        self.assertTrue(startup.is_enabled(self.key))
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.key) as key:
            self.assertEqual(winreg.QueryValueEx(key, startup.VALUE_NAME)[0], command)
        startup.set_enabled(False, command, self.key)
        startup.set_enabled(False, command, self.key)
        self.assertFalse(startup.is_enabled(self.key))
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.key) as key:
            self.assertEqual(winreg.QueryValueEx(key, 'UnrelatedApp')[0], 'unchanged')

    def test_missing_key_disable_is_safe(self):
        startup.set_enabled(False, '', self.key)
        self.assertFalse(startup.is_enabled(self.key))

    def test_packaged_command_quotes_paths_and_preserves_options(self):
        with patch.object(startup.sys, 'frozen', True, create=True), patch.object(
                startup.sys, 'executable', r'C:\My Apps\GHubIndicator.exe'):
            command = startup.launch_command(9011, r'C:\My Data\settings.db')
        self.assertEqual(command, r'"C:\My Apps\GHubIndicator.exe" --port 9011 --db "C:\My Data\settings.db"')

    def test_source_command_uses_pythonw_and_absolute_script(self):
        with tempfile.TemporaryDirectory() as folder:
            interpreter = Path(folder) / 'python.exe'
            interpreter.touch()
            interpreter.with_name('pythonw.exe').touch()
            with patch.object(startup.sys, 'frozen', False, create=True), patch.object(
                    startup.sys, 'executable', str(interpreter)):
                command = startup.launch_command()
            self.assertIn('pythonw.exe', command)
            self.assertIn(str(Path(startup.__file__).resolve().with_name('app.py')), command)

    def test_too_long_command_does_not_register(self):
        with self.assertRaises(ValueError):
            startup.set_enabled(True, 'x'*261, self.key)
        self.assertFalse(startup.is_enabled(self.key))


if __name__ == '__main__':
    unittest.main()
