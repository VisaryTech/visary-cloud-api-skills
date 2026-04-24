import os
from pathlib import Path
from urllib.parse import urlparse


def read_config_file(path):
    try:
        return Path(os.path.expanduser(path)).read_text(encoding="utf-8").strip()
    except Exception:
        return None


def derive_auth_base_url(base_url):
    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Invalid base_url")
    auth_host = parsed.netloc if parsed.netloc.startswith("id-") else f"id-{parsed.netloc}"
    return f"{parsed.scheme}://{auth_host}"


def resolve_token_url(base_url, config=None, env_names=()):
    config = config or {}
    explicit_token_url = config.get("tokenUrl")
    if explicit_token_url:
        return explicit_token_url.rstrip("/")

    for env_name in (*env_names, "VIS_TOKEN_URL", "visary_cloud_token_url"):
        value = os.getenv(env_name)
        if value:
            return value.rstrip("/")

    file_value = read_config_file("~/.config/visary_cloud/token_url")
    if file_value:
        return file_value.rstrip("/")

    auth_base_url = derive_auth_base_url(base_url)
    return f"{auth_base_url.rstrip('/')}/oidc/connect/token"


def resolve_client_credentials():
    client_id = (
        os.getenv("VIS_CLIENT_ID")
        or os.getenv("visary_cloud_client_id")
        or read_config_file("~/.config/visary_cloud/client_id")
    )
    client_secret = (
        os.getenv("VIS_CLIENT_SECRET")
        or os.getenv("visary_cloud_client_secret")
        or read_config_file("~/.config/visary_cloud/client_secret")
    )
    if not client_id or not client_secret:
        raise RuntimeError("Missing credentials: VIS_CLIENT_ID and/or VIS_CLIENT_SECRET")
    return client_id, client_secret


def get_access_token(requests_module, base_url, timeout=30, config=None, token_env_names=()):
    client_id, client_secret = resolve_client_credentials()
    token_url = resolve_token_url(base_url, config=config, env_names=token_env_names)
    try:
        response = requests_module.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=timeout,
        )
    except requests_module.Timeout as exc:
        raise TimeoutError(f"Token request timed out after {timeout} seconds: {token_url}") from exc
    except requests_module.RequestException as exc:
        raise RuntimeError(f"Token request failed: {token_url}: {exc}") from exc

    if not response.ok:
        try:
            error_body = response.json()
        except ValueError:
            error_body = response.text
        raise requests_module.HTTPError(
            f"HTTP {response.status_code} for token request {token_url}: {error_body}",
            response=response,
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise ValueError(f"Failed to decode token response JSON for {token_url}: {exc}") from exc

    access_token = payload.get("access_token")
    if not access_token:
        raise RuntimeError("Token response does not contain access_token")
    return str(access_token)
