import json

from playwright.sync_api import APIRequestContext

from tldw_Server_API.tests.webui_e2e.conftest import browser, page, server_url


def _patch_request_json_support() -> None:
    if getattr(APIRequestContext, "_tldw_json_patch", False):
        return

    def _wrap(method_name: str) -> None:
        original = getattr(APIRequestContext, method_name)

        def _patched(self, url, **kwargs):
            if "json" in kwargs:
                payload = kwargs.pop("json")
                headers = kwargs.pop("headers", None)
                headers = dict(headers) if headers else {}
                if not any(k.lower() == "content-type" for k in headers):
                    headers["Content-Type"] = "application/json"
                kwargs["headers"] = headers
                kwargs["data"] = json.dumps(payload)
            return original(self, url, **kwargs)

        setattr(APIRequestContext, method_name, _patched)

    for name in ("post", "put", "patch"):
        _wrap(name)

    APIRequestContext._tldw_json_patch = True


_patch_request_json_support()
