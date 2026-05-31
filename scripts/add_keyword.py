"""
keyword 테이블에 키워드 추가.
실행: python scripts/add_keyword.py --keyword "삼성전자" --portal NAVER
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from news_crawler.repository.db import db_context


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--keyword",  required=True)
    p.add_argument("--portal",   default="NAVER", choices=["NAVER", "DAUM", "GOOGLE", "WEIBO"])
    p.add_argument("--interval", default=86400, type=int, help="수집 주기(초), 기본 1일")
    p.add_argument("--priority", default=0, type=int)
    args = p.parse_args()

    with db_context() as engine:
        with engine.begin() as conn:
            result = conn.execute(
                text("""
                    INSERT INTO keyword (keyword, portal_type, interval_seconds, enabled, priority)
                    VALUES (:kw, :portal, :interval, true, :priority)
                    ON DUPLICATE KEY UPDATE
                        interval_seconds = VALUES(interval_seconds),
                        enabled = true,
                        priority = VALUES(priority)
                """),
                {"kw": args.keyword, "portal": args.portal,
                 "interval": args.interval, "priority": args.priority},
            )
            print(f"등록 완료: '{args.keyword}' [{args.portal}]  (affected rows: {result.rowcount})")


if __name__ == "__main__":
    main()
