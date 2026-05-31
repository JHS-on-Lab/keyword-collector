"""
Playwright 기반 headless 브라우저 Fetcher.

JS 렌더링이 필요한 페이지(SPA, 로딩 후 콘텐츠 표시 등)에 사용한다.
domain.render_mode = 'headless' 인 호스트에서 HttpFetcher 대신 호출된다.

사용하려면 Playwright 를 설치해야 한다:
  pip install playwright
  playwright install chromium

주의사항:
  - HttpFetcher 보다 느리고 리소스를 많이 쓴다. headless 가 꼭 필요한 도메인에만 설정할 것.
  - 브라우저를 매 요청마다 새로 띄우면 비효율적이므로 인스턴스를 재사용한다.
  - 사용 후 반드시 close() 를 호출해야 한다 (혹은 컨텍스트 매니저 사용).
"""

from __future__ import annotations

import time

from news_crawler.types import FetchResult, RenderMode


class HeadlessFetcher:
    """Playwright Chromium 으로 페이지를 렌더링해 HTML 을 반환한다."""

    def __init__(self, timeout_ms: int = 15000) -> None:
        self._timeout_ms = timeout_ms
        self._playwright = None
        self._browser    = None

    def _ensure_browser(self) -> None:
        """처음 호출 시 브라우저를 실행한다 (lazy init)."""
        if self._browser is not None:
            return
        from playwright.sync_api import sync_playwright
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)

    def fetch(self, url: str, *, render: RenderMode = RenderMode.HEADLESS) -> FetchResult:
        """URL 을 브라우저로 열어 렌더링된 HTML 을 반환한다."""
        self._ensure_browser()

        start = time.monotonic()
        page  = self._browser.new_page()
        try:
            response = page.goto(url, timeout=self._timeout_ms, wait_until="domcontentloaded")
            html     = page.content()
            status   = response.status if response else 200
        finally:
            page.close()

        elapsed_ms = (time.monotonic() - start) * 1000
        return FetchResult(
            url=url,
            html=html,
            status_code=status,
            render_mode=RenderMode.HEADLESS,
            elapsed_ms=elapsed_ms,
        )

    def close(self) -> None:
        """브라우저와 Playwright 를 정상 종료한다."""
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None

    def __enter__(self) -> "HeadlessFetcher":
        return self

    def __exit__(self, *_) -> None:
        self.close()
