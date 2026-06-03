"""
워커 프로세스 진입점.

실행 예:
  python -m news_crawler --role discovery  --portal naver
  python -m news_crawler --role extraction

역할(--role):
  discovery  → 키워드 스케줄을 돌면서 URL 을 수집한다 (dispatcher.py)
  extraction → 수집된 URL 에서 본문을 추출해 파일로 저장한다 (extraction_worker.py)
              + Reaper 를 daemon 스레드로 함께 시작한다

포털(--portal):
  naver / daum / google / all — discovery 워커가 어떤 포털 키워드를 처리할지 지정
  같은 포털로 워커를 여러 개 띄워도 서로 다른 키워드를 나눠 처리한다 (SKIP LOCKED)
"""

from __future__ import annotations

import argparse
import signal
import sys
import threading

from news_crawler import logging_setup
from news_crawler import config

_ROLES   = ("discovery", "extraction")
_PORTALS = ("naver", "daum", "google", "weibo", "naver_stock", "all")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="뉴스 크롤러 워커")
    p.add_argument("--role",   required=True, choices=_ROLES,   help="실행 역할")
    p.add_argument("--portal", default="all", choices=_PORTALS, help="포털 필터 (기본: all)")
    p.add_argument("--worker-id", default=None, help="워커 식별자 (기본: 환경변수 WORKER_ID)")
    return p.parse_args()


def _handle_signal(signum: int, frame: object) -> None:
    logger = logging_setup.setup("main")
    logger.info("shutdown", extra={"phase": "shutdown", "worker_id": config.WORKER_ID})
    sys.exit(0)


def main() -> None:
    args = _parse_args()
    config.validate()

    worker_id = args.worker_id or config.WORKER_ID
    config.WORKER_ID = worker_id  # FileSink 등 config를 직접 읽는 컴포넌트에 반영
    logger = logging_setup.setup(args.role, worker_id=worker_id)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT,  _handle_signal)

    logger.info(
        "starting",
        extra={"phase": "startup", "worker_id": worker_id},
    )

    try:
        if args.role == "discovery":
            from news_crawler.scheduling.dispatcher import run_discovery_loop
            run_discovery_loop(portal=args.portal, worker_id=worker_id)
        else:
            from news_crawler.worker.extraction_worker import run_extraction_loop
            from news_crawler.worker.reaper import run_reaper

            # daemon=True: 메인 루프(추출 워커)가 끝나면 Reaper 도 함께 종료된다.
            reaper = threading.Thread(
                target=run_reaper,
                args=(worker_id,),
                daemon=True,
                name="reaper",
            )
            reaper.start()
            run_extraction_loop(portal=args.portal, worker_id=worker_id)
    except Exception:
        logger.exception(
            "unhandled exception — worker stopping",
            extra={"phase": "main", "worker_id": worker_id},
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
