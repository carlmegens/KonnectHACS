"""Observed Konnect shapes, private projection, bounded caches and lifecycle races."""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from custom_components.ouderapp import content as module
from custom_components.ouderapp.api import OuderAppAuthError, OuderAppConnectionError, OuderAppError
from custom_components.ouderapp.content import OuderAppContent, OuderAppMediaError

URL = "https://resource.kidskonnect.cloud/photo.jpg?signature=private-signature"
PHOTO = {"mediumUrl": URL, "mediaType": "photo"}
TIMELINE = [
    {
        "type": "journal",
        "date": "2026-09-08",
        "journal": {
            "journalContent": f'<p>Fijne dag</p><script>secret-script</script><img src="{URL}">',
            "photos": [PHOTO],
            "writtenByName": "Medewerker",
            "private_unknown": "SECRET",
        },
    },
    {"type": "photo", "photos": [PHOTO]},
    {"type": "trigger", "description": "Consent request"},
]


async def test_projection_and_media_ids_separate_accounts_and_sources(hass):
    api = AsyncMock()
    api.async_get_timeline.return_value = TIMELINE
    api.async_get_conversation.return_value = [{"message": "Bericht", "photos": [PHOTO]}]
    feed, other, chat = (
        OuderAppContent(hass, api),
        OuderAppContent(hass, api),
        OuderAppContent(hass, api, messages=True),
    )
    first = await feed.async_get_content("timeline")
    second = await other.async_get_content("timeline")
    third = await chat.async_get_content("messages", conversation="1")
    assert len(first["items"]) == 2
    assert first["items"][0]["contents"] == "Fijne dag"
    assert first["items"][0]["sender"] == "Medewerker"
    handles = [result["items"][0]["images"][0]["id"] for result in (first, second, third)]
    assert len(set(handles)) == 3
    for secret in ("private-signature", "secret-script", "SECRET", "<", "https://"):
        assert secret not in json.dumps(first)
    with pytest.raises(OuderAppMediaError):
        await feed.async_get_image(handles[2])
    for cache in (feed, other, chat):
        await cache.async_close()


@pytest.mark.parametrize(
    "kind,method,row,title,text,date",
    [
        (
            "conversations",
            "async_get_messages",
            {
                "subject": "Opvang",
                "message": "Welkom",
                "date": "2026-09-08",
                "unread": True,
                "logMessageMessageId": 42,
            },
            "Opvang",
            "Welkom",
            "2026-09-08",
        ),
        (
            "news",
            "async_get_news",
            {
                "title": "Nieuws",
                "contentSnippet": "Morgen",
                "publishDate": "2026-09-08",
                "isNew": True,
            },
            "Nieuws",
            "Morgen",
            "2026-09-08",
        ),
        (
            "newsletters",
            "async_get_newsletters",
            {"mailSubject": "September", "contentSnippet": "Herfst", "sendDate": "2026-09-08"},
            "September",
            "Herfst",
            "2026-09-08",
        ),
    ],
)
async def test_observed_mailbox_fields(hass, kind, method, row, title, text, date):
    api = AsyncMock()
    getattr(api, method).return_value = [row]
    feed = OuderAppContent(hass, api, messages=kind == "conversations")
    result = await feed.async_get_content(kind)
    item = result["items"][0]
    assert (item["title"], item["contents"], item["created_at"]) == (title, text, date)
    assert item["conversation_id"] == ("42" if kind == "conversations" else None)
    await feed.async_close()


async def test_concurrent_reads_cache_copy_staleness_and_expiry(hass, monkeypatch):
    api = AsyncMock()
    api.async_get_timeline.return_value = TIMELINE
    feed = OuderAppContent(hass, api)
    clock = [0]
    monkeypatch.setattr(module, "_now", lambda: clock[0])
    results = await asyncio.gather(*(feed.async_get_content("timeline", limit=1) for _ in range(5)))
    api.async_get_timeline.assert_awaited_once_with(limit=20)
    results[0]["items"][0]["title"] = "MUTATED"
    assert results[1]["items"][0]["title"] == "Dagboek"
    api.async_get_timeline.side_effect = OuderAppConnectionError("private")
    clock[0] = 301
    assert (await feed.async_get_content("timeline"))["stale"] is True
    clock[0] = 3601
    with pytest.raises(OuderAppConnectionError):
        await feed.async_get_content("timeline")
    assert not feed._refs
    await feed.async_close()


async def test_auth_failure_never_returns_stale_and_purges_media(hass, monkeypatch):
    api = AsyncMock()
    api.async_get_timeline.return_value = TIMELINE
    feed = OuderAppContent(hass, api)
    clock = [0]
    monkeypatch.setattr(module, "_now", lambda: clock[0])
    await feed.async_get_content("timeline")
    clock[0] = 301
    api.async_get_timeline.side_effect = OuderAppAuthError("private")
    with pytest.raises(OuderAppAuthError):
        await feed.async_get_content("timeline")
    assert not feed._refs and not feed._feeds
    with pytest.raises(OuderAppError):
        await feed.async_get_content("timeline")
    await feed.async_close()


@pytest.mark.parametrize("failure", [False, True])
async def test_revocation_during_fetch_cannot_repopulate_or_serve_stale(hass, monkeypatch, failure):
    api = AsyncMock()
    feed = OuderAppContent(hass, api)
    api.async_get_timeline.return_value = TIMELINE
    clock = [0]
    monkeypatch.setattr(module, "_now", lambda: clock[0])
    await feed.async_get_content("timeline")
    clock[0] = 301
    started, release = asyncio.Event(), asyncio.Event()

    async def fetch(**kwargs):
        started.set()
        await release.wait()
        if failure:
            raise OuderAppConnectionError("private")
        return TIMELINE

    api.async_get_timeline.side_effect = fetch
    task = asyncio.create_task(feed.async_get_content("timeline"))
    await started.wait()
    feed.invalidate()
    release.set()
    with pytest.raises(OuderAppError):
        await task
    assert not feed._refs and not feed._feeds
    await feed.async_close()


async def test_media_reference_and_content_cache_budgets(hass, monkeypatch):
    api = AsyncMock()
    api.async_get_conversation.return_value = [{"message": "Hello"}]
    feed = OuderAppContent(hass, api, messages=True)
    monkeypatch.setattr(module, "MAX_MEDIA_REFS", 2)
    for number in range(10):
        feed._media_id(f"https://resource.kidskonnect.cloud/{number}")
        await feed.async_get_content("messages", conversation=str(number + 1))
    assert len(feed._refs) == len(feed._by_url) == 2
    assert len(feed._feeds) == module.MAX_FEED_CACHES
    await feed.async_close()


@pytest.mark.parametrize(
    "kind,options",
    [
        ("conversations", {}),
        ("messages", {"conversation": "1"}),
        ("timeline", {"limit": True}),
        ("timeline", {"limit": 21}),
        ("timeline", {"conversation": "1"}),
    ],
)
async def test_invalid_source_or_parameters_never_fetch(hass, kind, options):
    api = AsyncMock()
    feed = OuderAppContent(hass, api)
    with pytest.raises(OuderAppError):
        await feed.async_get_content(kind, **options)
    assert not api.mock_calls
    await feed.async_close()


async def test_transport_failure_backoff_bounds_concurrent_retries_and_recovers(hass, monkeypatch):
    clock = [1.0]
    monkeypatch.setattr(module, "_now", lambda: clock[0])
    api = AsyncMock()
    api.async_get_timeline.side_effect = OuderAppConnectionError("private")
    feed = OuderAppContent(hass, api)
    results = await asyncio.gather(
        *(feed.async_get_content("timeline") for _ in range(10)), return_exceptions=True
    )
    assert all(isinstance(value, OuderAppConnectionError) for value in results)
    api.async_get_timeline.assert_awaited_once()
    assert feed._retry_at == 31
    clock[0] = 31
    with pytest.raises(OuderAppConnectionError):
        await feed.async_get_content("timeline")
    assert feed._retry_at == 91
    clock[0] = 91
    api.async_get_timeline.side_effect = None
    api.async_get_timeline.return_value = TIMELINE
    assert (await feed.async_get_content("timeline"))["returned"] == 2
    assert feed._failures == 0 and feed._retry_at == 0
    await feed.async_close()


@pytest.mark.parametrize(
    "kind,field", [("news", "htmlContentId"), ("newsletters", "generatedHtmlNewsLetterId")]
)
async def test_article_is_on_demand_plain_text_and_separately_cached(hass, kind, field):
    api = AsyncMock()
    row = {
        field: 42,
        "title": "Title",
        "contentSnippet": "Preview",
        "detail_html": "PROVIDER-FIELD-MUST-NOT-LEAK",
    }
    getattr(api, "async_get_news" if kind == "news" else "async_get_newsletters").return_value = [
        row
    ]
    api.async_get_article.return_value = [
        {
            **row,
            "detail_html": "<style>"
            + "x" * 22000
            + '</style><p>Complete body</p><iframe src="https://private.invalid"></iframe><script>private-script</script>',
        }
    ]
    feed = OuderAppContent(hass, api)
    listing = await feed.async_get_content(kind)
    api.async_get_article.assert_not_awaited()
    assert listing["items"][0]["article_id"] == "42"
    assert listing["items"][0]["contents"] == "Preview"
    assert not listing["detail"]
    detail = await feed.async_get_content(kind, article="42")
    assert detail["detail"]
    assert detail["items"][0]["contents"] == "Complete body"
    assert detail["items"][0]["images"] == []
    assert not detail["items"][0]["truncated"]
    assert (await feed.async_get_content(kind, article="42")) == detail
    api.async_get_article.assert_awaited_once_with(kind, "42")
    assert (await feed.async_get_content(kind))["items"][0]["contents"] == "Preview"
    for source, article in (("timeline", "42"), ("messages", "42"), (kind, "../42"), (kind, 42)):
        with pytest.raises(OuderAppError):
            await feed.async_get_content(source, article=article)
    await feed.async_close()


async def test_article_cache_stale_then_auth_failure_and_late_invalidation(hass, monkeypatch):
    now = 1000
    monkeypatch.setattr(module, "_now", lambda: now)
    api = AsyncMock()
    api.async_get_article.return_value = [{"htmlContentId": 42, "detail_html": "x" * 25000}]
    feed = OuderAppContent(hass, api)
    result = await feed.async_get_content("news", article="42")
    assert result["items"][0]["truncated"]
    assert len(result["items"][0]["contents"]) == 20000
    now += 301
    api.async_get_article.side_effect = OuderAppConnectionError()
    assert (await feed.async_get_content("news", article="42"))["stale"]
    now += 301
    api.async_get_article.side_effect = OuderAppAuthError()
    with pytest.raises(OuderAppAuthError):
        await feed.async_get_content("news", article="42")
    assert not feed._feeds
    await feed.async_close()
    feed = OuderAppContent(hass, api)

    async def invalidate(*args):
        feed.invalidate()
        return [{"htmlContentId": 42, "detail_html": "late private"}]

    api.async_get_article.side_effect = invalidate
    with pytest.raises(OuderAppError):
        await feed.async_get_content("news", article="42")
    assert not feed._feeds
    await feed.async_close()


async def test_news_detail_photos_are_private_bounded_deduplicated_and_invalidated(hass):
    api = AsyncMock()
    candidates = [{"mediumUrl": "https://other.invalid/private"}, PHOTO, PHOTO] + [
        {"mediumUrl": f"https://resource.kidskonnect.cloud/{index}.jpg?secret=token"}
        for index in range(6)
    ]
    row = {"htmlContentId": 42, "generatedHtmlNewsLetterId": 42, "detail_photos": candidates}
    api.async_get_news.return_value = [row]
    api.async_get_article.return_value = [{**row, "detail_html": "News body"}]
    feed, other, chat = (
        OuderAppContent(hass, api),
        OuderAppContent(hass, api),
        OuderAppContent(hass, api, messages=True),
    )
    try:
        assert (await feed.async_get_content("news"))["items"][0]["images"] == []
        first = await feed.async_get_content("news", article="42")
        second = await other.async_get_content("news", article="42")
        images = first["items"][0]["images"]
        assert len(images) == len({image["id"] for image in images}) == 3
        assert images != second["items"][0]["images"]
        assert "https://" not in str(first) and "token" not in str(first)
        assert (await feed.async_get_content("newsletters", article="42"))["items"][0][
            "images"
        ] == []
        for image in images:
            with pytest.raises(OuderAppMediaError):
                await other.async_get_image(image["id"])
            with pytest.raises(OuderAppMediaError):
                await chat.async_get_image(image["id"])
        feed.invalidate()
        assert not feed._refs and not feed._images
        for image in images:
            with pytest.raises(OuderAppError):
                await feed.async_get_image(image["id"])
    finally:
        await feed.async_close()
        await other.async_close()
        await chat.async_close()
