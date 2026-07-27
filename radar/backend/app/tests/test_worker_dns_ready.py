"""DNS readiness gate before Miniflux refresh_all_feeds."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.worker import WorkerState, _drain_unread, wait_for_external_dns


@pytest.mark.unit
@pytest.mark.asyncio
async def test_wait_for_external_dns_ok_first_try() -> None:
    loop = AsyncMock()
    loop.getaddrinfo = AsyncMock(return_value=[(None, None, None, None, ("93.184.216.34", 443))])

    with patch("app.worker.asyncio.get_running_loop", return_value=loop):
        ok = await wait_for_external_dns(host="example.com", retries=3, delay_seconds=0)

    assert ok is True
    assert loop.getaddrinfo.await_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_wait_for_external_dns_retries_then_ok() -> None:
    loop = AsyncMock()
    loop.getaddrinfo = AsyncMock(
        side_effect=[
            OSError("no such host"),
            OSError("no such host"),
            [(None, None, None, None, ("1.2.3.4", 443))],
        ]
    )

    with (
        patch("app.worker.asyncio.get_running_loop", return_value=loop),
        patch("app.worker.asyncio.sleep", new_callable=AsyncMock) as sleep_mock,
    ):
        ok = await wait_for_external_dns(host="example.com", retries=3, delay_seconds=0.01)

    assert ok is True
    assert loop.getaddrinfo.await_count == 3
    assert sleep_mock.await_count == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_wait_for_external_dns_exhausted() -> None:
    loop = AsyncMock()
    loop.getaddrinfo = AsyncMock(side_effect=OSError("no such host"))

    with (
        patch("app.worker.asyncio.get_running_loop", return_value=loop),
        patch("app.worker.asyncio.sleep", new_callable=AsyncMock),
    ):
        ok = await wait_for_external_dns(host="example.com", retries=2, delay_seconds=0)

    assert ok is False
    assert loop.getaddrinfo.await_count == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_drain_skips_refresh_when_dns_not_ready() -> None:
    state = WorkerState()
    state.miniflux_client = AsyncMock()
    state.miniflux_client.refresh_all_feeds = AsyncMock()
    state.miniflux_client.fetch_unread_entries = AsyncMock(return_value=[])

    with (
        patch("app.worker.wait_for_external_dns", new_callable=AsyncMock, return_value=False),
        patch("app.worker.run_pipeline_cycle", new_callable=AsyncMock, return_value=False),
        patch("app.worker.WORKER_REFRESH_SETTLE_SECONDS", 5),
        patch("app.worker.asyncio.sleep", new_callable=AsyncMock) as sleep_mock,
    ):
        await _drain_unread(state, settle=True)

    state.miniflux_client.refresh_all_feeds.assert_not_awaited()
    sleep_mock.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_drain_refreshes_when_dns_ready() -> None:
    state = WorkerState()
    state.miniflux_client = AsyncMock()
    state.miniflux_client.refresh_all_feeds = AsyncMock()

    with (
        patch("app.worker.wait_for_external_dns", new_callable=AsyncMock, return_value=True),
        patch("app.worker.run_pipeline_cycle", new_callable=AsyncMock, return_value=False),
        patch("app.worker.WORKER_REFRESH_SETTLE_SECONDS", 0),
    ):
        await _drain_unread(state, settle=True)

    state.miniflux_client.refresh_all_feeds.assert_awaited_once()
