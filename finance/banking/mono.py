"""Small server-side Mono Connect API client.

Never put the secret key in a template/browser. This client does not initiate
payments and never handles bank passwords, PINs, or OTPs.
"""
import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

BASE_URL = "https://api.withmono.com/v2"


class MonoAPIError(RuntimeError):
    """A safe, user-displayable Mono API error."""


class MonoClient:
    def __init__(self, secret_key=None, timeout=20):
        if secret_key is None:
            from django.conf import settings
            secret_key = getattr(settings, "MONO_SECRET_KEY", "")
        self.secret_key = (secret_key or "").strip()
        self.timeout = timeout
        if not self.secret_key:
            raise MonoAPIError("Mono is not configured. Ask an administrator to configure the server credentials.")

    def request(self, path, query="", method="GET", body=None):
        url = f"{BASE_URL}{path}" + (f"?{query}" if query else "")
        headers = {
            "Accept": "application/json",
            "mono-sec-key": self.secret_key,
        }
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            # Do not return provider response bodies to end users; they may contain
            # account details. Keep the status code only.
            raise MonoAPIError(f"Mono API request failed (HTTP {exc.code}).") from exc
        except (URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise MonoAPIError("Could not retrieve data from Mono. Check the connection and try again.") from exc
        if not isinstance(payload, dict) or payload.get("status") == "error" or payload.get("status") == "failed":
            raise MonoAPIError("Mono returned an unsuccessful response.")
        return payload

    def initiate_account_linking(self, *, customer_name, customer_email, reference, redirect_url):
        """Create a hosted Mono Connect Link session for the signed-in depot user."""
        return self.request(
            "/accounts/initiate",
            method="POST",
            body={
                "customer": {"name": customer_name, "email": customer_email},
                "scope": "auth",
                "meta": {"ref": reference},
                "redirect_url": redirect_url,
            },
        )

    def account_details(self, account_id):
        return self.request(f"/accounts/{quote(str(account_id), safe='')}")

    def balance(self, account_id):
        return self.request(f"/accounts/{quote(str(account_id), safe='')}/balance")

    def transactions(self, account_id, page=1):
        return self.request(
            f"/accounts/{quote(str(account_id), safe='')}/transactions",
            f"page={int(page)}",
        )
