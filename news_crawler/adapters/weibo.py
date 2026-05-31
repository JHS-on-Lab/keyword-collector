"""웨이보 발견 어댑터 (전략 미확정) — 7단계에서 구현."""

from __future__ import annotations

from news_crawler.types import DiscoverResult, PortalType


class WeiboAdapter:
    portal_type: str = PortalType.WEIBO

    def discover(self, keyword: str, cursor: str | None) -> DiscoverResult:
        raise NotImplementedError
