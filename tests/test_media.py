"""Photo validation and cache tests; all media and transport responses are synthetic."""

import asyncio
import socket
from io import BytesIO
from threading import get_ident
from unittest.mock import AsyncMock

import aiohttp
import pytest
from PIL import Image, PngImagePlugin

from custom_components.ouderapp import content as feed_module
from custom_components.ouderapp.content import (
    OuderAppContent,
    OuderAppMediaError,
    _decode_image,
    _public_ip,
    _PublicResolver,
    _validated_url,
)


def image_bytes(kind="PNG", size=(32, 24)):
    result = BytesIO()
    picture = Image.new("RGB", size, "#224466")
    if kind == "PNG":
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("private", "synthetic-secret-metadata")
        picture.save(result, kind, pnginfo=metadata)
    elif kind == "JPEG":
        exif = Image.Exif()
        exif[270] = "synthetic-secret-metadata"
        picture.save(result, kind, exif=exif)
    else:
        picture.save(result, kind)
    return result.getvalue()


@pytest.mark.parametrize(
    "url",
    [
        "https://93.184.216.34/photo",
        "https://resource.kidskonnect.cloud.evil.invalid/photo",
        "https://resource.kidskonnect.cloud./photo",
        "https://storage.googleapis.com/photo",
        "http://resource.kidskonnect.cloud/photo",
        "file:///tmp/photo.jpg",
        "https://localhost/photo",
        "https://localhost./photo",
        "https://printer.local/photo",
        "https://host.internal/photo",
        "https://127.0.0.1/photo",
        "https://10.2.3.4/photo",
        "https://192.168.1.1/photo",
        "https://169.254.169.254/latest/meta-data",
        "https://100.64.0.1/photo",
        "https://[::1]/photo",
        "https://[::ffff:127.0.0.1]/photo",
        "https://[64:ff9b::7f00:1]/photo",
        "https://１２７.０.０.１/photo",
        "https://@resource.kidskonnect.cloud/photo",
        "https://synthetic-user:synthetic-secret@resource.kidskonnect.cloud/photo",
        "https://resource.kidskonnect.cloud:8443/photo",
        "https://resource.kidskonnect.cloud:not-a-port/photo",
        "https://[invalid/photo",
        "https://resource.kidskonnect.cloud/photo#secret",
        "https://resource.kidskonnect.cloud/photo#",
        " https://resource.kidskonnect.cloud/photo",
        "https://resource.kidskonnect.cloud/\nphoto",
    ],
)
def test_photo_urls_reject_private_or_ambiguous_destinations(url):
    with pytest.raises(OuderAppMediaError) as error:
        _validated_url(url)
    assert str(error.value) == "The OuderApp photo is unavailable"


@pytest.mark.parametrize(
    "url",
    [
        "https://resource.kidskonnect.cloud/photo?signature=synthetic",
    ],
)
def test_photo_urls_allow_https_public_targets(url):
    assert _validated_url(url) == url


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "0.0.0.0",
        "255.255.255.255",
        "224.0.0.1",
        "100.64.0.1",
        "192.0.2.1",
        "fe80::1",
        "::1",
        "fc00::1",
        "ff02::1",
        "64:ff9b::a00:1",
        "2002:0a00:0001::1",
        "not-an-ip",
    ],
)
def test_resolved_ip_guard_rejects_non_public_and_transition_addresses(address):
    assert not _public_ip(address)


def answer(address):
    return {
        "hostname": "resource.kidskonnect.cloud",
        "host": address,
        "port": 443,
        "family": socket.AF_INET,
        "proto": socket.IPPROTO_TCP,
        "flags": socket.AI_NUMERICHOST,
    }


async def test_guarded_resolver_returns_exact_validated_answers_and_blocks_rebinding():
    resolver = _PublicResolver()
    answers = [answer("93.184.216.34")]
    resolver._resolver.resolve = AsyncMock(side_effect=[answers, [answer("127.0.0.1")]])
    assert await resolver.resolve("resource.kidskonnect.cloud", 443) is answers
    with pytest.raises(OuderAppMediaError):
        await resolver.resolve("resource.kidskonnect.cloud", 443)
    await resolver.close()


async def test_mixed_public_private_dns_answer_fails_closed():
    resolver = _PublicResolver()
    resolver._resolver.resolve = AsyncMock(
        return_value=[answer("93.184.216.34"), answer("10.0.0.1")]
    )
    with pytest.raises(OuderAppMediaError):
        await resolver.resolve("resource.kidskonnect.cloud", 443)
    await resolver.close()


async def test_private_session_uses_guarded_dns_without_credentials_or_cookie_storage(hass):
    feed = OuderAppContent(hass, AsyncMock())
    session = feed._get_session()
    assert session.connector._resolver is feed._resolver
    assert session.connector.use_dns_cache is False
    assert session.connector.force_close is True
    assert isinstance(session.cookie_jar, aiohttp.DummyCookieJar)
    assert session.trust_env is False
    assert "Authorization" not in session.headers
    assert "Cookie" not in session.headers
    assert session._default_auth is None
    await feed.async_close()
    assert session.closed


class FakeResponse:
    def __init__(self, status=200, data=b"", headers=None, content_length=None):
        self.status = status
        self.data = data
        self.headers = headers or {}
        self.content_length = content_length
        self.content = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def iter_chunked(self, size):
        for index in range(0, len(self.data), size):
            yield self.data[index : index + size]


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def get(self, url, **kwargs):
        self.requests.append((url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.mark.parametrize(
    "location",
    [
        "https://127.0.0.1/private",
        "http://resource.kidskonnect.cloud/private",
        "https://user:secret@resource.kidskonnect.cloud/private",
        "https://１２７.０.０.１/private",
    ],
)
async def test_redirect_destinations_are_checked_before_a_second_request(
    hass, monkeypatch, location
):
    feed = OuderAppContent(hass, AsyncMock())
    session = FakeSession([FakeResponse(302, headers={"Location": location})])
    monkeypatch.setattr(feed, "_get_session", lambda: session)
    with pytest.raises(OuderAppMediaError):
        await feed._download("https://resource.kidskonnect.cloud/source")
    assert len(session.requests) == 1
    assert session.requests[0][1] == {"allow_redirects": False}
    await feed.async_close()


async def test_redirects_have_a_finite_request_budget(hass, monkeypatch):
    feed = OuderAppContent(hass, AsyncMock())
    session = FakeSession([FakeResponse(302, headers={"Location": "/again"})] * 5)
    monkeypatch.setattr(feed, "_get_session", lambda: session)
    with pytest.raises(OuderAppMediaError):
        await feed._download("https://resource.kidskonnect.cloud/source")
    assert len(session.requests) == feed_module.MAX_REDIRECTS + 1
    await feed.async_close()


async def test_valid_redirect_forwards_no_auth_or_cookies(hass, monkeypatch):
    feed = OuderAppContent(hass, AsyncMock())
    session = FakeSession(
        [
            FakeResponse(
                302,
                headers={
                    "Location": "https://resource.kidskonnect.cloud/photo",
                    "Set-Cookie": "secret=cookie",
                },
            ),
            FakeResponse(data=b"synthetic-image"),
        ]
    )
    monkeypatch.setattr(feed, "_get_session", lambda: session)
    assert await feed._download("https://resource.kidskonnect.cloud/source") == b"synthetic-image"
    assert all(kwargs == {"allow_redirects": False} for _, kwargs in session.requests)
    await feed.async_close()


@pytest.mark.parametrize(
    "response",
    [
        FakeResponse(403, data=b"synthetic-secret"),
        FakeResponse(200, data=b"compressed", headers={"Content-Encoding": "gzip"}),
        FakeResponse(200, data=b"small", content_length=11),
        FakeResponse(200, data=b"x" * 11),
        aiohttp.ClientError("https://private.invalid/synthetic-secret"),
        TimeoutError("synthetic-secret"),
    ],
)
async def test_http_errors_compression_and_oversized_data_fail_safely(
    hass, monkeypatch, caplog, response
):
    monkeypatch.setattr(feed_module, "MAX_DOWNLOAD_BYTES", 10)
    feed = OuderAppContent(hass, AsyncMock())
    session = FakeSession([response])
    monkeypatch.setattr(feed, "_get_session", lambda: session)
    with pytest.raises(OuderAppMediaError) as error:
        await feed._download("https://resource.kidskonnect.cloud/source?secret=synthetic-secret")
    assert "synthetic-secret" not in str(error.value)
    assert "synthetic-secret" not in caplog.text
    await feed.async_close()


@pytest.mark.parametrize("kind", ["JPEG", "PNG", "WEBP"])
def test_actual_decode_reencodes_supported_photos_and_strips_metadata(kind):
    data = _decode_image(image_bytes(kind))
    assert b"synthetic-secret" not in data
    with Image.open(BytesIO(data)) as picture:
        assert picture.format == "JPEG"
        assert picture.size == (32, 24)
        assert not picture.getexif()
        assert "icc_profile" not in picture.info


def test_large_photo_is_resized_with_aspect_ratio_preserved():
    with Image.open(BytesIO(_decode_image(image_bytes(size=(2000, 1000))))) as picture:
        assert picture.size == (1600, 800)


@pytest.mark.parametrize(
    "data",
    [
        b"<svg>synthetic-secret</svg>",
        b"<html>synthetic-secret</html>",
        b"not-an-image",
        image_bytes("GIF"),
    ],
)
def test_non_photos_cannot_pass_by_claiming_an_image_content_type(data):
    with pytest.raises(OuderAppMediaError):
        _decode_image(data)


def test_pixel_limit_checked_before_full_decode(monkeypatch):
    monkeypatch.setattr(feed_module, "MAX_IMAGE_PIXELS", 100)
    with pytest.raises(OuderAppMediaError):
        _decode_image(image_bytes(size=(11, 10)))


def test_output_byte_limit_is_enforced(monkeypatch):
    monkeypatch.setattr(feed_module, "MAX_OUTPUT_BYTES", 10)
    with pytest.raises(OuderAppMediaError):
        _decode_image(image_bytes())


async def test_image_decode_runs_off_loop_and_is_cached_then_expires(hass, monkeypatch):
    feed = OuderAppContent(hass, AsyncMock())
    clock = [100.0]
    monkeypatch.setattr(feed_module, "_now", lambda: clock[0])
    media_id = feed._media_id("https://resource.kidskonnect.cloud/source")
    download = AsyncMock(return_value=image_bytes())
    monkeypatch.setattr(feed, "_download", download)
    threads = []
    original_decode = feed_module._decode_image

    def decode(data):
        threads.append(get_ident())
        return original_decode(data)

    monkeypatch.setattr(feed_module, "_decode_image", decode)
    first, second = await asyncio.gather(
        feed.async_get_image(media_id), feed.async_get_image(media_id)
    )
    assert first == second
    assert first[1] == "image/jpeg"
    download.assert_awaited_once()
    assert threads and all(thread != get_ident() for thread in threads)
    clock[0] += feed_module.IMAGE_TTL + 1
    await feed.async_get_image(media_id)
    assert download.await_count == 2
    await feed.async_close()
    assert not feed._images


async def test_decoded_photo_cache_obeys_entry_and_total_byte_limits(hass, monkeypatch):
    feed = OuderAppContent(hass, AsyncMock())
    monkeypatch.setattr(feed_module, "MAX_CACHED_IMAGES", 2)
    encoded = _decode_image(image_bytes())
    monkeypatch.setattr(feed_module, "MAX_IMAGE_CACHE_BYTES", len(encoded) + 1)
    monkeypatch.setattr(feed, "_download", AsyncMock(return_value=image_bytes()))
    for index in range(4):
        await feed.async_get_image(feed._media_id(f"https://resource.kidskonnect.cloud/{index}"))
    assert len(feed._images) == 1
    assert sum(len(item.data) for item in feed._images.values()) <= len(encoded) + 1
    await feed.async_close()


@pytest.mark.parametrize(
    "media_id",
    ["../secret", "https://resource.kidskonnect.cloud/source", "a" * 31, "a" * 33, "a" * 32, None],
)
async def test_only_existing_opaque_photo_handles_are_fetchable(hass, media_id):
    feed = OuderAppContent(hass, AsyncMock())
    with pytest.raises(OuderAppMediaError):
        await feed.async_get_image(media_id)
    await feed.async_close()
