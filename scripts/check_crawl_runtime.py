"""
t_crawl_runtime 테이블 조회 확인 스크립트.

실행:
  python scripts/check_crawl_runtime.py [runtime_name]

인수 없으면 테이블 전체 목록을 출력한다.
인수 있으면 해당 runtime_name 의 solr_url 을 조회한다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.repository.db import db_context
from app.repository.crawl_runtime_repo import CrawlRuntimeRepo
from sqlalchemy import text


def main() -> None:
    runtime_name = sys.argv[1] if len(sys.argv) > 1 else None

    with db_context() as engine:
        if runtime_name:
            repo = CrawlRuntimeRepo(engine)
            solr_url = repo.get_solr_url(runtime_name)
            if solr_url:
                print(f"runtime_name : {runtime_name}")
                print(f"solr_url     : {solr_url}")
            else:
                print(f"[없음] runtime_name='{runtime_name}' 인 행이 없거나 use_yn='N' 입니다.")
                sys.exit(1)
        else:
            with engine.connect() as conn:
                rows = conn.execute(
                    text("SELECT runtime_name, crawler_type, solr_url, use_yn FROM t_crawl_runtime ORDER BY runtime_name")
                ).fetchall()

            if not rows:
                print("t_crawl_runtime 테이블이 비어 있습니다.")
                return

            print(f"{'runtime_name':<30} {'crawler_type':<20} {'use_yn':<6} solr_url")
            print("-" * 100)
            for row in rows:
                print(f"{row[0]:<30} {(row[1] or ''):<20} {row[3]:<6} {row[2] or ''}")


if __name__ == "__main__":
    main()
