import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "visary_cloud_common.py"


def load_common_module():
    spec = importlib.util.spec_from_file_location("visary_cloud_common_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CommonConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_common_module()

    def test_reads_single_json_config_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "visary-cloud.json"
            config_path.write_text(
                """
                {
                  "apiBaseUrl": "https://vis.example",
                  "tokenUrl": "https://id-vis.example/oidc/connect/token",
                  "clientId": "client-id",
                  "clientSecret": "client-secret"
                }
                """,
                encoding="utf-8",
            )

            with patch.object(self.module, "CONFIG_FILE_PATH", str(config_path)):
                self.assertEqual(
                    "https://vis.example",
                    self.module.read_config_value("apiBaseUrl"),
                )
                self.assertEqual(
                    "https://id-vis.example/oidc/connect/token",
                    self.module.resolve_token_url("https://vis.example"),
                )

                with patch.dict("os.environ", {}, clear=True):
                    self.assertEqual(
                        ("client-id", "client-secret"),
                        self.module.resolve_client_credentials(),
                    )

    def test_missing_json_value_returns_none(self):
        with patch.object(self.module, "read_user_config", return_value={}):
            self.assertIsNone(self.module.read_config_value("apiBaseUrl"))


if __name__ == "__main__":
    unittest.main()
