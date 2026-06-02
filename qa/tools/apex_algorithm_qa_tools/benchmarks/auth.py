import time

import requests


def _discover_oidc_endpoints(keycloak_url: str, realm: str) -> tuple[str, list[str]]:
    """Resolve token and device authorization endpoints from OIDC discovery.

    Falls back to well-known Keycloak endpoint patterns when discovery is unavailable.
    """

    base = keycloak_url.rstrip("/")
    fallback_token = f"{base}/realms/{realm}/protocol/openid-connect/token"
    fallback_devices = [
        f"{base}/realms/{realm}/protocol/openid-connect/auth/device",
        f"{base}/realms/{realm}/protocol/openid-connect/device/auth",
    ]

    discovery_url = f"{base}/realms/{realm}/.well-known/openid-configuration"
    try:
        response = requests.get(discovery_url, timeout=30)
        response.raise_for_status()
        discovery = response.json()
        token_url = discovery.get("token_endpoint") or fallback_token
        device_url = discovery.get("device_authorization_endpoint")
        device_urls = [device_url] if device_url else []
        device_urls.extend(fallback_devices)
        # Keep ordering stable while avoiding duplicates.
        device_urls = list(dict.fromkeys(device_urls))
        return token_url, device_urls
    except Exception:
        return fallback_token, fallback_devices


def _safe_json(response: requests.Response) -> dict:
    try:
        data = response.json()
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}


def get_token_with_client_credentials(
    keycloak_url: str,
    realm: str,
    client_id: str,
    client_secret: str,
) -> str:
    """Retrieve an access token from a Keycloak instance using client credentials (client ID + secret).

    :param keycloak_url: Base URL of the Keycloak instance (e.g. https://keycloak.example.com).
    :param realm: Keycloak realm name.
    :param client_id: Client ID registered in Keycloak.
    :param client_secret: Client secret associated with the client ID.
    :return: Access token string.
    """
    token_url = f"{keycloak_url.rstrip('/')}/realms/{realm}/protocol/openid-connect/token"
    response = requests.post(
        token_url,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def get_token_with_device_flow(
    keycloak_url: str,
    realm: str,
    client_id: str,
    poll_interval: int = 5,
    timeout: int = 300,
) -> str:
    """Retrieve an access token from a Keycloak instance using the OAuth2 device authorization flow.

    This will print a user code and verification URL to the console, then poll until
    the user completes authentication or the timeout is reached.

    :param keycloak_url: Base URL of the Keycloak instance (e.g. https://keycloak.example.com).
    :param realm: Keycloak realm name.
    :param client_id: Client ID registered in Keycloak.
    :param poll_interval: Seconds to wait between polling attempts (default: 5).
    :param timeout: Maximum seconds to wait for the user to authenticate (default: 300).
    :return: Access token string.
    """
    token_url, device_urls = _discover_oidc_endpoints(keycloak_url, realm)

    device_response = None
    for device_url in device_urls:
        candidate = requests.post(device_url, data={"client_id": client_id}, timeout=30)
        if candidate.status_code in {404, 405}:
            continue
        device_response = candidate
        break

    if device_response is None:
        raise RuntimeError(f"Could not find a working device authorization endpoint. Tried: {device_urls!r}")

    if device_response.status_code == 401:
        error_payload = _safe_json(device_response)
        error = error_payload.get("error")
        error_description = error_payload.get("error_description")
        raise RuntimeError(
            "Device-flow authorization request was rejected (401). "
            "This usually means client or realm configuration mismatch. "
            "Verify: 1) realm is correct, 2) client_id exists in that realm, "
            "3) client allows device authorization grant, 4) client is public "
            "or otherwise configured for device flow. "
            f"endpoint={device_response.url!r} error={error!r} "
            f"error_description={error_description!r}"
        )

    device_response.raise_for_status()
    device_data = device_response.json()

    device_code = device_data["device_code"]
    user_code = device_data["user_code"]
    verification_uri = device_data.get("verification_uri_complete") or device_data["verification_uri"]
    interval = device_data.get("interval", poll_interval)

    print(f"To authenticate, visit: {verification_uri}")
    print(f"And enter the code: {user_code}")

    elapsed = 0
    while elapsed < timeout:
        time.sleep(interval)
        elapsed += interval

        token_response = requests.post(
            token_url,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "client_id": client_id,
                "device_code": device_code,
            },
            timeout=30,
        )

        if token_response.status_code == 200:
            return token_response.json()["access_token"]

        error_data = _safe_json(token_response)
        error = error_data.get("error")
        if error == "authorization_pending":
            continue
        elif error == "slow_down":
            interval += 5
        else:
            token_response.raise_for_status()

    raise TimeoutError(f"Device flow authentication timed out after {timeout} seconds.")
