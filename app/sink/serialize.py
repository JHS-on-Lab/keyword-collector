"""
Article → dict 직렬화 — Solr 스키마 필드명 기준.

FileSink 와 SolrSink 가 동일한 키 이름을 쓰도록 공유한다.

필드명 매핑:
  url_hash     → id
  body         → content
  published_at → postdate  (없으면 생략)
  collected_at → tstamp

SolrSink 는 Solr 스키마에 없는 필드를 추가로 제거한다.
FileSink 는 반환값 전체(Solr 외 필드 포함)를 그대로 저장한다.
"""

from __future__ import annotations

import dataclasses
from urllib.parse import urlparse

from app.types import Article


def to_doc(article: Article) -> dict:
    """Article 을 Solr 스키마 기준 키 이름의 dict 로 변환한다."""
    d = dataclasses.asdict(article)
    doc: dict = {
        "id":          d.pop("url_hash"),
        "url":         d["url"],
        "host":        urlparse(d["url"]).netloc,
        "title":       d["title"],
        "content":     d["body"],
        "tstamp":      d["collected_at"].isoformat() + "Z",
        "source_type": d["source_type"],
        "keyword":     d["keyword"],
        "author":      d["author"],
        "extraction_method": d["extraction_method"],
        "body_len":    d["body_len"],
    }
    if d["published_at"] is not None:
        doc["postdate"] = d["published_at"].isoformat() + "Z"
    return doc


# SolrSink 가 전송할 필드 — 스키마에 존재하는 것만
_SOLR_FIELDS = {"id", "url", "host", "title", "content", "postdate", "tstamp"}


def to_solr_doc(article: Article) -> dict:
    """Solr 스키마에 있는 필드만 포함한 dict 를 반환한다."""
    return {k: v for k, v in to_doc(article).items() if k in _SOLR_FIELDS}
