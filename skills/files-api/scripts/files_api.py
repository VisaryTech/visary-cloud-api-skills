import base64
import json
import os
from pathlib import Path
import sys
from urllib.parse import quote
from urllib.parse import urlparse


COMMON_SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"
if str(COMMON_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_SCRIPTS_DIR))

import requests
from visary_cloud_common import get_access_token, read_config_file


SKILL_ROOT = Path(__file__).resolve().parent.parent
INDEX_DIR = SKILL_ROOT / "assets" / "index"
MANIFEST_PATH = INDEX_DIR / "manifest.json"


class FilesAPI:
    @staticmethod
    def _read_file(path):
        return read_config_file(path)

    @classmethod
    def _resolve_base_url(cls, config=None):
        config = config or {}
        explicit = config.get("endpoint")
        if explicit:
            return str(explicit).rstrip("/")

        generic = (
            os.getenv("VIS_API_BASE_URL")
            or os.getenv("visary_cloud_api_base_url")
            or cls._read_file("~/.config/visary_cloud/api_base_url")
        )
        if not generic:
            raise ValueError("Missing Visary Cloud files endpoint")

        generic = generic.rstrip("/")
        lower_generic = generic.lower()
        if lower_generic.endswith("/files"):
            return generic
        parsed = urlparse(generic)
        if parsed.scheme and parsed.netloc:
            return f"{generic}/files"
        raise ValueError("Invalid Visary Cloud files base_url")

    @classmethod
    def _resolve_token_url(cls, base_url, config=None):
        from visary_cloud_common import resolve_token_url

        return resolve_token_url(base_url, config=config, env_names=("VIS_FILES_TOKEN_URL", "visary_cloud_files_token_url"))

    @classmethod
    def _get_access_token(cls, base_url, timeout=30, config=None):
        return get_access_token(
            requests,
            base_url,
            timeout=timeout,
            config=config,
            token_env_names=("VIS_FILES_TOKEN_URL", "visary_cloud_files_token_url"),
        )

    @staticmethod
    def _load_operations():
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        operations = {}
        for item in manifest.get("indexes", []):
            index_path = SKILL_ROOT / item["file"]
            payload = json.loads(index_path.read_text(encoding="utf-8"))
            for entry in payload.get("methods", []):
                operations[entry["pythonMethod"]] = entry
        return operations

    def __init__(self, timeout=30, headers=None, config=None):
        self.config = dict(config or {})
        self.base_url = self._resolve_base_url(config=self.config)
        self.headers = dict(headers or {})
        self.timeout = timeout
        self.token = self._get_access_token(self.base_url, timeout=timeout, config=self.config)
        self.operations = self._load_operations()

    def call_by_python_method(self, python_method, *args, save_to=None, **kwargs):
        operation = self.operations.get(python_method)
        if operation is None:
            raise AttributeError(f"FilesAPI has no method {python_method}")

        path = operation["path"]
        remaining_positionals = list(args)
        keyword_args = dict(kwargs)

        for param in operation.get("pathParams", []):
            if remaining_positionals:
                value = remaining_positionals.pop(0)
            elif param in keyword_args:
                value = keyword_args.pop(param)
            else:
                raise ValueError(f"Missing required path parameter: {param}")
            path = path.replace("{" + param + "}", quote(str(value), safe=""))

        if remaining_positionals:
            raise ValueError(f"Unexpected positional arguments: {remaining_positionals}")

        params = {}
        for param in operation.get("queryParams", []):
            if param in keyword_args:
                params[param] = keyword_args.pop(param)

        json_body = None
        if operation.get("hasBody"):
            if "body" in keyword_args:
                json_body = keyword_args.pop("body")
            else:
                body_fields = operation.get("bodyFields", [])
                extracted = {}
                for field in body_fields:
                    if field in keyword_args:
                        extracted[field] = keyword_args.pop(field)
                if extracted:
                    json_body = extracted
            if operation.get("bodyRequired") and json_body is None:
                json_body = {}

        if keyword_args:
            raise ValueError(
                "Unknown arguments for "
                f"{python_method}: {', '.join(sorted(keyword_args))}"
            )

        return self._request(
            operation["httpMethod"],
            path,
            params=params or None,
            json_body=json_body,
            save_to=save_to,
        )

    def _request(self, method, path, *, params=None, json_body=None, save_to=None):
        request_headers = dict(self.headers)
        if self.token is not None and "Authorization" not in request_headers:
            request_headers["Authorization"] = (
                self.token if str(self.token).startswith("Bearer ") else f"Bearer {self.token}"
            )

        url = f"{self.base_url}{path}"
        try:
            response = requests.request(
                method=method,
                url=url,
                params=params,
                json=json_body,
                headers=request_headers,
                timeout=self.timeout,
            )
        except requests.Timeout as exc:
            raise TimeoutError(f"Request timed out after {self.timeout} seconds: {method} {path}") from exc
        except requests.RequestException as exc:
            raise RuntimeError(f"Request failed: {method} {path}: {exc}") from exc

        if not response.ok:
            try:
                error_body = response.json()
            except ValueError:
                error_body = response.text
            raise requests.HTTPError(
                f"HTTP {response.status_code} for {method} {path}: {error_body}",
                response=response,
            )

        if method.upper() == "HEAD":
            return self._head_result(response)

        if save_to:
            target = Path(save_to)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(response.content)
            return {
                "savedTo": str(target),
                "statusCode": response.status_code,
                "contentType": response.headers.get("Content-Type"),
                "contentLength": len(response.content),
            }

        if response.status_code in (204, 205) or not response.content:
            return None

        content_type = response.headers.get("Content-Type", "")
        if any(token in content_type for token in ("application/json", "+json", "text/json")):
            try:
                return response.json()
            except ValueError as exc:
                raise ValueError(f"Failed to decode JSON response for {method} {path}: {exc}") from exc

        if content_type.startswith("text/") or "text/plain" in content_type:
            return response.text

        try:
            return response.json()
        except ValueError:
            if self._looks_like_text(response.content):
                return response.text

        if len(response.content) > 4096:
            raise ValueError(
                "Binary response is larger than 4096 bytes. Use --save-to <path> to write it to disk."
            )

        return {
            "contentType": content_type or None,
            "contentLength": len(response.content),
            "contentBase64": base64.b64encode(response.content).decode("ascii"),
        }

    @staticmethod
    def _head_result(response):
        return {
            "statusCode": response.status_code,
            "headers": dict(response.headers),
            "contentLength": response.headers.get("Content-Length"),
            "contentType": response.headers.get("Content-Type"),
        }

    @staticmethod
    def _looks_like_text(content):
        if not content:
            return True
        try:
            content.decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False
