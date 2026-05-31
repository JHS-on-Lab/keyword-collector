"""
구글 뉴스 발견 어댑터.

전략: Google News RSS 피드 사용.
  - HTML 스크래핑 / headless 없이 공식 RSS로 기사 목록 획득
  - URL: news.google.com/rss/search?q=키워드&hl=ko&gl=KR&ceid=KR:ko
  - 기사 링크는 news.google.com/rss/articles/CBM... 리다이렉트 URL
    → 추출 단계에서 실제 언론사 URL로 리다이렉트 추적
  - guid로 중복 제거 (같은 기사가 다른 키워드로 들어와도 동일 guid)
  - RSS는 페이지네이션 없음 → 최대 100개 반환 (Google 정책)
  - 날짜 필터: pubDate 기준으로 cutoff_days 이내 기사만 선택

커서: 지원하지 않음 (RSS는 단일 응답). cursor는 항상 None 반환.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

from news_crawler.fetch._client import make_client
from news_crawler.types import DiscoverResult, PortalType

_RSS_URL = "https://news.google.com/rss/search"

_DEFAULT_CUTOFF_DAYS = 1   # 하루치


class GoogleAdapter:
    portal_type: str = PortalType.GOOGLE

    def __init__(self, cutoff_days: int = _DEFAULT_CUTOFF_DAYS) -> None:
        self._cutoff_days = cutoff_days

    def discover(self, keyword: str, cursor: str | None) -> DiscoverResult:
        # RSS는 페이지네이션 없음 — cursor가 이미 있으면 완료
        if cursor is not None:
            return DiscoverResult(urls=[], next_cursor=None, has_more=False)

        params = {
            "q":    keyword,
            "hl":   "ko",
            "gl":   "KR",
            "ceid": "KR:ko",
        }

        with make_client() as client:
            resp = client.get(_RSS_URL, params=params)
            resp.raise_for_status()

        urls = _parse_rss(resp.content, cutoff_days=self._cutoff_days)
        return DiscoverResult(urls=urls, next_cursor=None, has_more=False)


def _parse_rss(content: bytes, cutoff_days: int) -> list[str]:
    """
    RSS XML 파싱 → 기사 URL 목록.
    - guid를 URL로 사용 (중복 제거 기준).
    - pubDate 기준 cutoff_days 이내 기사만 포함.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=cutoff_days)
    root = ET.fromstring(content)
    channel = root.find("channel")
    if channel is None:
        return []

    urls: list[str] = []
    for item in channel.findall("item"):
        link    = item.findtext("link", "").strip()
        guid    = item.findtext("guid", "").strip()
        pubdate = item.findtext("pubDate", "").strip()

        if not link:
            continue

        # 날짜 필터
        if pubdate:
            try:
                pub_dt = parsedate_to_datetime(pubdate)
                if pub_dt < cutoff:
                    continue
            except Exception:
                pass  # 날짜 파싱 실패 시 포함

        # link(전체 URL)를 저장. guid는 link의 suffix라 normalize 후 url_hash로 중복 제거됨
        urls.append(link)

    return urls
