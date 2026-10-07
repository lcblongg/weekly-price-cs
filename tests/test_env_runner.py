import tempfile
import unittest
from pathlib import Path
from tools.env_runner import read_environment


class EnvironmentRunnerTests(unittest.TestCase):
    def read(self, text):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '.env'
            path.write_text(text)
            return read_environment(path)

    def test_quoted_secrets_empty_values_and_literal_shell_characters(self):
        result = self.read('# cấu hình\nTOKEN="literal$(command)"\nURL=https://example.com/#fragment\nEMPTY=\nexport LABEL="a b"')
        self.assertEqual(result, dict(TOKEN='literal$(command)',
                                     URL='https://example.com/#fragment', EMPTY='', LABEL='a b'))

    def test_invalid_value_error_does_not_disclose_secret(self):
        with self.assertRaises(ValueError) as result:
            self.read('TOKEN="private-secret')
        self.assertNotIn('private-secret', str(result.exception))
