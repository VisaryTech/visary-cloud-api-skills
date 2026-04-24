import os
from pathlib import Path
import sys


COMMON_SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"
if str(COMMON_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_SCRIPTS_DIR))

import requests
from visary_cloud_common import get_access_token, read_config_file


class CalendarAPI:
    @staticmethod
    def _read_file(path):
        return read_config_file(path)

    @classmethod
    def _resolve_base_url(cls, config=None):
        resolved = os.getenv("VIS_API_BASE_URL") or cls._read_file("~/.config/visary_cloud/api_base_url")
        if not resolved:
            raise ValueError("Missing Visary Cloud calendar endpoint")
        return f"{resolved.rstrip('/')}/calendar"

    @classmethod
    def _resolve_token_url(cls, base_url, config=None):
        from visary_cloud_common import resolve_token_url

        return resolve_token_url(base_url, config=config, env_names=("visary_cloud_calendar_token_url",))

    @classmethod
    def _get_access_token(cls, base_url, timeout=30, config=None):
        return get_access_token(
            requests,
            base_url,
            timeout=timeout,
            config=config,
            token_env_names=("visary_cloud_calendar_token_url",),
        )

    def __init__(self, timeout=30, headers=None, config=None):
        self.config = dict(config or {})
        self.base_url = self._resolve_base_url(config=self.config)
        self.headers = dict(headers or {})
        self.timeout = timeout
        self.token = self._get_access_token(self.base_url, timeout=timeout, config=self.config)

    def call_by_python_method(self, python_method, *args, **kwargs):
        method = getattr(self, python_method, None)
        if method is None:
            raise AttributeError(f"CalendarAPI has no method {python_method}")
        return method(*args, **kwargs)

    def _request(self, method, path, *, params=None, json_body=None, data=None, headers=None, files=None, raw=False):
        request_headers = dict(self.headers)
        if self.token is not None and "Authorization" not in request_headers:
            request_headers["Authorization"] = (
                self.token if str(self.token).startswith("Bearer ") else f"Bearer {self.token}"
            )
        if headers:
            request_headers.update(headers)
        url = f"{self.base_url}{path}"
        try:
            response = requests.request(
                method=method,
                url=url,
                params=params,
                json=json_body,
                data=data,
                headers=request_headers,
                files=files,
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

        if raw:
            return response

        if response.status_code in (204, 205) or not response.content:
            return None

        content_type = response.headers.get("Content-Type", "")
        expects_json = any(token in content_type for token in ("application/json", "+json", "text/json"))
        if expects_json:
            try:
                return response.json()
            except ValueError as exc:
                raise ValueError(f"Failed to decode JSON response for {method} {path}: {exc}") from exc

        try:
            return response.json()
        except ValueError:
            return response.text if response.text != "" else None

    def get_calendar(self):
        return self._request("GET", "/calendar")

    def post_calendar(self, *, body=None):
        return self._request("POST", "/calendar", json_body=body)

    def get_calendar_by_owner_id_owner_id(self, owner_id):
        return self._request("GET", f"/calendar/byOwnerId/{owner_id}")

    def get_calendar_id(self, id):
        return self._request("GET", f"/calendar/{id}")

    def patch_calendar_id(self, id, *, body=None):
        return self._request("PATCH", f"/calendar/{id}", json_body=body)

    def delete_calendar_id(self, id):
        return self._request("DELETE", f"/calendar/{id}")

    def get_calendar_export_id(self, id, *, start=None, end=None, file_name=None):
        params = {}
        if start is not None:
            params["start"] = start
        if end is not None:
            params["end"] = end
        if file_name is not None:
            params["fileName"] = file_name
        if not params:
            params = None
        return self._request("GET", f"/calendar/export/{id}", params=params, raw=True)

    def post_calendar_import_id(self, id, *, file_path):
        with Path(file_path).expanduser().open("rb") as handle:
            files = {"file": (Path(file_path).name, handle)}
            return self._request("POST", f"/calendar/import/{id}", files=files)

    def get_event(self, *, calendar_id=None, start=None, end=None):
        params = {}
        if calendar_id is not None:
            params["calendarId"] = calendar_id
        if start is not None:
            params["start"] = start
        if end is not None:
            params["end"] = end
        if not params:
            params = None
        return self._request("GET", "/event", params=params)

    def post_event(self, *, body=None):
        return self._request("POST", "/event", json_body=body)

    def patch_event(self, *, body=None):
        return self._request("PATCH", "/event", json_body=body)

    def get_event_id(self, id):
        return self._request("GET", f"/event/{id}")

    def delete_event_id(self, id):
        return self._request("DELETE", f"/event/{id}")

    def get_permission(self, *, calendar_id=None):
        params = {}
        if calendar_id is not None:
            params["calendarId"] = calendar_id
        if not params:
            params = None
        return self._request("GET", "/permission", params=params)

    def post_permission(self, *, body=None):
        return self._request("POST", "/permission", json_body=body)

    def patch_permission(self, *, body=None):
        return self._request("PATCH", "/permission", json_body=body)

    def get_permission_id(self, id):
        return self._request("GET", f"/permission/{id}")

    def delete_permission_id(self, id):
        return self._request("DELETE", f"/permission/{id}")
