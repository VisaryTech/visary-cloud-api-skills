import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "subskills" / "files-api" / "scripts" / "files_api.py"


def load_files_api_module():
    spec = importlib.util.spec_from_file_location("files_api_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class Response:
    def __init__(self, *, status_code=200, headers=None, content=b'{"ok": true}'):
        self.status_code = status_code
        self.headers = dict(headers or {"Content-Type": "application/json"})
        self.content = content

    @property
    def ok(self):
        return 200 <= self.status_code < 400

    @property
    def text(self):
        return self.content.decode("utf-8")

    def json(self):
        import json

        return json.loads(self.text)


class FilesAPIDynamicDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_files_api_module()

    def make_api(self):
        api = object.__new__(self.module.FilesAPI)
        api.config = {}
        api.base_url = "https://vis.example/files"
        api.headers = {}
        api.timeout = 30
        api.token = "test-token"
        api.operations = self.module.FilesAPI._load_operations()
        return api

    def test_path_params_are_url_encoded(self):
        calls = []

        def fake_request(**kwargs):
            calls.append(kwargs)
            return Response()

        api = self.make_api()
        with patch.object(self.module.requests, "request", side_effect=fake_request):
            api.call_by_python_method("get_drives_by_label_label", "team/a? b")

        self.assertEqual("GET", calls[0]["method"])
        self.assertEqual(
            "https://vis.example/files/drives/by_label/team%2Fa%3F%20b",
            calls[0]["url"],
        )

    def test_query_params_are_forwarded_and_unknown_args_raise(self):
        calls = []

        def fake_request(**kwargs):
            calls.append(kwargs)
            return Response()

        api = self.make_api()
        with patch.object(self.module.requests, "request", side_effect=fake_request):
            api.call_by_python_method("get_items", drive_id=12, take=50, skip=10)

        self.assertEqual({"drive_id": 12, "take": 50, "skip": 10}, calls[0]["params"])

        with self.assertRaises(ValueError):
            api.call_by_python_method("get_items", unsupported=True)

    def test_body_fields_are_collected_into_json_body(self):
        calls = []

        def fake_request(**kwargs):
            calls.append(kwargs)
            return Response()

        api = self.make_api()
        with patch.object(self.module.requests, "request", side_effect=fake_request):
            api.call_by_python_method("post_items", drive_id=12, directory_id=34, name="Specs")

        self.assertEqual("POST", calls[0]["method"])
        self.assertEqual({"drive_id": 12, "directory_id": 34}, calls[0]["params"])
        self.assertEqual({"name": "Specs"}, calls[0]["json"])

    def test_save_to_writes_binary_response_and_returns_metadata(self):
        api = self.make_api()
        response = Response(
            headers={"Content-Type": "application/octet-stream"},
            content=b"\x00\x01file-bytes",
        )

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "download.bin"
            with patch.object(self.module.requests, "request", return_value=response):
                result = api.call_by_python_method(
                    "get_files_download",
                    drive_id=12,
                    item_id=99,
                    save_to=target,
                )

            self.assertEqual(b"\x00\x01file-bytes", target.read_bytes())
            self.assertEqual(str(target), result["savedTo"])
            self.assertEqual(200, result["statusCode"])
            self.assertEqual("application/octet-stream", result["contentType"])
            self.assertEqual(12, result["contentLength"])

    def test_head_response_returns_metadata(self):
        api = self.make_api()
        response = Response(
            headers={"Content-Type": "application/pdf", "Content-Length": "1234"},
            content=b"",
        )

        with patch.object(self.module.requests, "request", return_value=response):
            result = api.call_by_python_method("head_files_download", drive_id=12, item_id=99)

        self.assertEqual(200, result["statusCode"])
        self.assertEqual("1234", result["contentLength"])
        self.assertEqual("application/pdf", result["contentType"])
        self.assertEqual(
            {"Content-Type": "application/pdf", "Content-Length": "1234"},
            result["headers"],
        )


if __name__ == "__main__":
    unittest.main()
