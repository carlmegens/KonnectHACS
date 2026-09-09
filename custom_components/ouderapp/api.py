"""Bounded async Konnect client based on the public parent web application.

Only authentication uses PUT. Content requests are GETs. No browser, credential
store or SDK file storage is used. Provider responses never enter exceptions.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

import httpx

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_ITEMS = 100
PORTAL_RE = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
# Client protocol selected by the official app's HTTP interceptor. Keep this
# separate from our integration version and HomeAssistant-OuderApp User-Agent.
# Public parent build main.c77f420466dc9cc6.js, inspected 2026-09-09.
PROVIDER_CLIENT_VERSION = "3.64.1"


class OuderAppError(Exception):
    """Unsupported response, without provider content."""


class OuderAppResponseError(OuderAppError):
    """Finite diagnostic identifiers, never provider values or request details."""

    def __init__(self, reason: str, stage: str = "unknown", status: int | None = None) -> None:
        reasons = {
            "provider_rejected",
            "response_shape",
            "http_status",
            "invalid_json",
            "too_large",
            "account_destination",
            "missing_access_token",
            "missing_refresh_token",
            "invalid_token",
            "account_identity",
            "unknown",
        }
        stages = {"captcha", "login", "refresh", "identity", "parent", "content", "unknown"}
        self.reason = reason if reason in reasons else "unknown"
        self.stage = stage if stage in stages else "unknown"
        self.status = status if type(status) is int and 100 <= status <= 599 else None
        super().__init__(self.code)

    @property
    def code(self) -> str:
        suffix = f"_{self.status}" if self.reason == "http_status" and self.status else ""
        return f"{self.stage}.{self.reason}{suffix}"


def _response_stage(path: str) -> str:
    return {
        "/auth-api/captcha": "captcha",
        "/auth-api/login": "login",
        "/auth-api/token": "refresh",
        "/auth-api/user": "identity",
        "/restservices-parent/parent": "parent",
    }.get(path, "content")


class OuderAppAuthError(OuderAppError):
    """An account needs to sign in again."""


class OuderAppConnectionError(OuderAppError):
    """Transient transport or provider failure."""


class OuderAppInteractionRequired(OuderAppAuthError):
    """The parent must resolve an account step in the official portal."""


def normalize_portal(value: str) -> str:
    """Accept a tenant or its exact HTTPS hostname, never an arbitrary URL."""
    if not isinstance(value, str):
        raise ValueError("Invalid portal")
    value = value.strip().lower()
    if value.startswith("https://"):
        parsed = urlsplit(value)
        if parsed.netloc != parsed.hostname or parsed.path not in ("", "/"):
            raise ValueError("Invalid portal")
        if parsed.query or parsed.fragment:
            raise ValueError("Invalid portal")
        value = parsed.hostname or ""
    if value.endswith(".ouderportaal.nl"):
        value = value.removesuffix(".ouderportaal.nl")
    if not PORTAL_RE.fullmatch(value):
        raise ValueError("Invalid portal")
    return value


def account_key(portal: str, username: str) -> str:
    """Derive identity only from the username confirmed by /auth-api/user."""
    return hashlib.sha256(f"{portal}\0{username.strip().casefold()}".encode()).hexdigest()


def _unwrap(value: Any) -> Any:
    if isinstance(value, dict) and value.get("result") is False:
        raise OuderAppResponseError("provider_rejected")
    if (
        isinstance(value, dict)
        and "payload" in value
        and (type(value.get("result")) is bool or set(value) <= {"payload", "messages"})
    ):
        return value["payload"]
    return value


def _object(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OuderAppResponseError("response_shape")
    return value


def _items(value: Any, *keys: str) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        value = next((value[key] for key in keys if key in value), None)
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise OuderAppError("Unexpected list shape")
    return value[:MAX_ITEMS]


def _counter(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


@dataclass(repr=False)
class Session:
    """Only these fields can be persisted; never a password or cookie jar."""

    portal: str
    username: str
    account_id: str
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    device_info: dict[str, Any] = field(repr=False)

    def storage(self) -> dict[str, Any]:
        return {
            "portal": self.portal,
            "username": self.username,
            "account_id": self.account_id,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "device_info": dict(self.device_info),
        }


class OuderAppApi:
    """Own a separate HTTP client and single refresh lock for each account."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        portal: str,
        session: Session | None = None,
        on_session: Callable[[Session], Awaitable[None]] | None = None,
    ) -> None:
        self.client = client
        self.portal = normalize_portal(portal)
        self.base = f"https://{self.portal}.ouderportaal.nl"
        if session and (
            session.portal != self.portal
            or session.account_id != account_key(self.portal, session.username)
            or not session.access_token
            or not session.refresh_token
        ):
            raise OuderAppAuthError("Invalid stored account")
        self.session = session
        self.on_session = on_session
        self._refresh_lock = asyncio.Lock()
        self.auth_failed = False
        self.closed = False

    async def async_close(self) -> None:
        if self.closed:
            return
        self.closed = True
        await self.client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        if self.closed:
            raise OuderAppConnectionError("Client closed")
        if not path.startswith(("/auth-api/", "/restservices-parent/")):
            raise ValueError("Unsupported route")
        headers = {
            "Accept": "application/json",
            "X-Client-Name": "OuderApp",
            "X-Client-Version": PROVIDER_CLIENT_VERSION,
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            async with self.client.stream(
                method,
                self.base + path,
                headers=headers,
                json=body,
                params=params,
                follow_redirects=False,
                timeout=30,
            ) as response:
                status = response.status_code
                if status == 429 or status >= 500:
                    raise OuderAppConnectionError("Provider temporarily unavailable")
                if status in (401, 403):
                    raise OuderAppAuthError("Authentication rejected")
                if status == 400 and path.startswith("/auth-api/"):
                    raise OuderAppAuthError("Authentication rejected")
                if status != 200:
                    raise OuderAppResponseError("http_status", _response_stage(path), status)
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > MAX_RESPONSE_BYTES:
                        raise OuderAppResponseError("too_large", _response_stage(path))
        except httpx.HTTPError, TimeoutError:
            raise OuderAppConnectionError("Unable to reach provider") from None
        try:
            return _unwrap(json.loads(data))
        except OuderAppResponseError as error:
            if error.reason == "provider_rejected" and path in (
                "/auth-api/login",
                "/auth-api/token",
            ):
                raise OuderAppAuthError("Authentication rejected") from None
            raise OuderAppResponseError(error.reason, _response_stage(path)) from None
        except ValueError, UnicodeError:
            raise OuderAppResponseError("invalid_json", _response_stage(path)) from None

    def _tokens(self, body: Any, previous: Session | None = None) -> tuple[str, str]:
        stage = "refresh" if previous else "login"
        if not isinstance(body, dict):
            raise OuderAppResponseError("response_shape", stage)
        data = body
        if data.get("mustResetPassword"):
            raise OuderAppInteractionRequired("Complete account step in parent portal")
        destination = data.get("domainServerName")
        if destination and destination not in (self.portal, f"{self.portal}.ouderportaal.nl"):
            raise OuderAppResponseError("account_destination", stage)
        redirect = data.get("redirectUrl")
        if redirect is not None and (
            not isinstance(redirect, str)
            or not (redirect == "/parent" or redirect.startswith("/parent/"))
        ):
            raise OuderAppInteractionRequired("Parent account required")
        access = data.get("authToken")
        refresh = data.get("refreshToken") or (previous.refresh_token if previous else None)
        if access is None or access == "":
            raise OuderAppResponseError("missing_access_token", stage)
        if refresh is None or refresh == "":
            raise OuderAppResponseError("missing_refresh_token", stage)
        if not all(isinstance(v, str) and 0 < len(v) <= 32768 for v in (access, refresh)):
            raise OuderAppResponseError("invalid_token", stage)
        return access, refresh

    async def _identity(self, token: str) -> tuple[str, str]:
        user = await self._request("GET", "/auth-api/user", token=token)
        if not isinstance(user, dict):
            raise OuderAppResponseError("response_shape", "identity")
        username = user.get("username")
        if not isinstance(username, str) or not username.strip() or len(username) > 320:
            raise OuderAppResponseError("account_identity", "identity")
        return username.strip(), account_key(self.portal, username)

    async def async_login(
        self,
        username: str,
        password: str,
        device_info: dict[str, Any],
    ) -> Session:
        captcha = await self._request("GET", "/auth-api/captcha")
        if isinstance(captcha, dict) and captcha.get("blockedUntil"):
            raise OuderAppInteractionRequired("Complete account step in parent portal")
        result = await self._request(
            "PUT",
            "/auth-api/login",
            body={
                "username": username.strip(),
                "password": password,
                "deviceInfo": device_info,
            },
        )
        access, refresh = self._tokens(result)
        canonical_name, identity = await self._identity(access)
        # Prove parent access before accepting a session from a shared login API.
        parent = await self._request("GET", "/restservices-parent/parent", token=access)
        if not isinstance(parent, dict):
            raise OuderAppResponseError("response_shape", "parent")
        self.session = Session(
            self.portal, canonical_name, identity, access, refresh, dict(device_info)
        )
        self.auth_failed = False
        return self.session

    async def _refresh(self, rejected_token: str) -> None:
        async with self._refresh_lock:
            if self.auth_failed or not self.session:
                raise OuderAppAuthError("Sign in again")
            old = self.session
            if old.access_token != rejected_token:
                return
            try:
                result = await self._request(
                    "PUT",
                    "/auth-api/token",
                    token=old.access_token,
                    body={
                        "username": old.username,
                        "refreshToken": old.refresh_token,
                        "connectionType": "unknown",
                        "deviceInfo": old.device_info,
                    },
                )
                access, refresh = self._tokens(result, old)
                username, identity = await self._identity(access)
                if identity != old.account_id:
                    raise OuderAppAuthError("Account changed")
            except OuderAppAuthError:
                self.auth_failed = True
                raise
            current = Session(self.portal, username, identity, access, refresh, old.device_info)
            if self.on_session:
                await self.on_session(current)
            self.session = current

    async def _get(self, path: str, **params: Any) -> Any:
        if self.auth_failed or not self.session:
            raise OuderAppAuthError("Sign in again")
        token = self.session.access_token
        try:
            return await self._request(
                "GET", "/restservices-parent" + path, token=token, params=params
            )
        except OuderAppAuthError:
            await self._refresh(token)
        try:
            return await self._request(
                "GET", "/restservices-parent" + path, token=self.session.access_token, params=params
            )
        except OuderAppAuthError:
            self.auth_failed = True
            raise

    async def async_validate_account(self) -> None:
        """Validate stored credentials through a refreshable parent request."""
        _object(await self._get("/parent"))
        assert self.session
        _, identity = await self._identity(self.session.access_token)
        if identity != self.session.account_id:
            self.auth_failed = True
            raise OuderAppAuthError("Account changed")

    async def async_fetch_summary(self) -> dict[str, int | None]:
        children = _items(await self._get("/children/"), "activeChildren")
        notifications = _object(await self._get("/notification/notifications"))
        return {
            "children_count": len(children) if len(children) < MAX_ITEMS else None,
            "unread_messages": _counter(notifications.get("nrOfNewMessages")),
            "unread_news": _counter(notifications.get("nrOfNewNewsItems")),
        }

    async def async_get_timeline(self, limit: int = 20) -> list[dict[str, Any]]:
        self._limit(limit)
        return _items(await self._get("/timeline/cards/v2/0"), "items", "cards")[:limit]

    async def async_get_messages(self, limit: int = 20) -> list[dict[str, Any]]:
        self._limit(limit)
        return _items(await self._get("/logbook/overview", index=0))[:limit]

    async def async_get_newsletters(self, limit: int = 20) -> list[dict[str, Any]]:
        self._limit(limit)
        return _items(await self._get("/newsletter", index=0), "newsletterItems")[:limit]

    async def async_get_news(self, limit: int = 20) -> list[dict[str, Any]]:
        self._limit(limit)
        return _items(await self._get("/htmlnews/view"))[:limit]

    async def async_get_article(self, kind: str, article: str) -> list[dict[str, Any]]:
        """Read one article only after proving membership of this account/source."""
        if (
            kind not in ("news", "newsletters")
            or not isinstance(article, str)
            or not re.fullmatch(r"[0-9]{1,20}", article)
            or int(article) <= 0
        ):
            raise ValueError("Invalid article")
        if kind == "news":
            rows = await self.async_get_news(20)
            field, route = "htmlContentId", "/htmlcontent/container/"
        else:
            rows = await self.async_get_newsletters(20)
            field, route = "generatedHtmlNewsLetterId", "/newsletter/generated/"
        row = next(
            (
                item
                for item in rows
                if type(item.get(field)) in (int, str) and str(item[field]) == article
            ),
            None,
        )
        if row is None:
            raise OuderAppError("Article unavailable in this account/source")
        detail = _object(await self._get(route + article))
        if kind == "newsletters":
            html = detail.get("fullSource")
            if not isinstance(html, str):
                raise OuderAppError("Unexpected article shape")
        else:
            sections = _items(detail, "items")
            parts = []
            for section in sections:
                for part in _items(section, "itemParts"):
                    value = part.get("content")
                    if value is not None and not isinstance(value, str):
                        raise OuderAppError("Unexpected article shape")
                    if value:
                        parts.append(value)
            html = "\n".join(parts)
        return [{**row, "detail_html": html}]

    async def async_get_conversation(
        self, conversation: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        self._limit(limit)
        if (
            not isinstance(conversation, str)
            or not re.fullmatch(r"[0-9]{1,20}", conversation)
            or int(conversation) <= 0
        ):
            raise ValueError("Invalid conversation")
        rows = await self.async_get_messages(20)
        if not any(
            type(row.get("logMessageMessageId")) in (int, str)
            and str(row["logMessageMessageId"]) == conversation
            for row in rows
        ):
            raise OuderAppError("Conversation unavailable in this account")
        result = _object(await self._get(f"/logbook/details/{conversation}/summary/true"))
        # Return the latest messages when the server provides a chronological thread.
        rows = result.get("messages")
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise OuderAppError("Unexpected list shape")
        return rows[-limit:]

    @staticmethod
    def _limit(limit: int) -> None:
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("Limit must be between 1 and 50")
