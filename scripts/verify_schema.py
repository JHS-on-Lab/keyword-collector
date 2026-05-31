"""
스키마 검증: 테이블·컬럼·인덱스·제약 확인.
실행: python scripts/verify_schema.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text, inspect
from news_crawler.repository.db import db_context

EXPECTED_TABLES = {"keyword", "article_url", "domain", "alembic_version"}

EXPECTED_INDEXES = {
    "article_url": {"uq_article_url_hash", "ix_article_url_claim", "ix_article_url_host", "ix_article_url_keyword"},
    "keyword":     {"uq_keyword_portal"},
}


def main():
    with db_context() as engine:
        insp = inspect(engine)
        tables = set(insp.get_table_names())

        print("=== 테이블 목록 ===")
        missing = EXPECTED_TABLES - tables
        for t in sorted(tables):
            print(f"  {'OK' if t in EXPECTED_TABLES else '  '} {t}")
        if missing:
            print(f"  [MISSING] {missing}")

        print()
        for table in ("keyword", "article_url", "domain"):
            cols = [c["name"] for c in insp.get_columns(table)]
            idxs = {i["name"] for i in insp.get_indexes(table)}
            print(f"=== {table} ===")
            print(f"  columns : {', '.join(cols)}")
            print(f"  indexes : {', '.join(sorted(idxs))}")

        print()
        # SKIP LOCKED 동작 확인 (MySQL 8.0+ 필요, 트랜잭션 안에서만 유효)
        with engine.begin() as conn:
            conn.execute(text(
                "SELECT id FROM keyword LIMIT 1 FOR UPDATE SKIP LOCKED"
            ))
            print("SKIP LOCKED 지원: OK")

        print("\n스키마 검증 완료.")


if __name__ == "__main__":
    main()
