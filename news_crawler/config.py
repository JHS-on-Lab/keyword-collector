"""
환경변수에서 설정을 읽는다.

값은 .env 파일 또는 실제 환경변수 어느 쪽에서든 넣을 수 있다.
서버에서는 보통 환경변수로, 로컬 개발에서는 .env 파일로 설정한다.
.env 파일이 없어도 오류가 나지 않는다.

필수 변수(RDS_*)가 없으면 워커 시작 시 validate() 가 오류를 출력하고 종료한다.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# .env 파일을 읽어 환경변수에 추가한다. 이미 설정된 환경변수는 덮어쓰지 않는다.
load_dotenv(Path(__file__).parent.parent / ".env")


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _env_int(key: str, default: int) -> int:
    return int(os.getenv(key, str(default)))


def _env_bool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).lower() in ("true", "1", "yes")


# SSH Tunnel
TUNNEL_ENABLED      = _env_bool("TUNNEL_ENABLED")
TUNNEL_SSH_HOST     = _env("TUNNEL_SSH_HOST")
TUNNEL_SSH_PORT     = _env_int("TUNNEL_SSH_PORT", 22)
TUNNEL_SSH_USER     = _env("TUNNEL_SSH_USER", "ubuntu")
TUNNEL_SSH_KEY_PATH = _env("TUNNEL_SSH_KEY_PATH")
TUNNEL_LOCAL_PORT   = _env_int("TUNNEL_LOCAL_PORT", 13306)

# RDS
RDS_HOST     = _env("RDS_HOST")
RDS_PORT     = _env_int("RDS_PORT", 3306)
RDS_USER     = _env("RDS_USER")
RDS_PASSWORD = _env("RDS_PASSWORD")
RDS_DB       = _env("RDS_DB")

# Worker
WORKER_ID              = _env("WORKER_ID", "worker-1")
EXTRACTION_CONCURRENCY = _env_int("EXTRACTION_CONCURRENCY", 4)

# Fetcher
DEFAULT_CRAWL_DELAY_MS = _env_int("DEFAULT_CRAWL_DELAY_MS", 1000)
DEFAULT_RENDER_MODE    = _env("DEFAULT_RENDER_MODE", "static")
PROXY_PROVIDER         = _env("PROXY_PROVIDER", "direct")

# Sink
SINK_TYPE       = _env("SINK_TYPE", "file")   # file | solr
FILE_SINK_DIR   = _env("FILE_SINK_DIR", "./data")
LOG_DIR         = _env("LOG_DIR", "./logs")

# Solr (SINK_TYPE=solr 일 때만 필요)
SOLR_URL        = _env("SOLR_URL", "")         # 예: http://localhost:8983/solr/news
SOLR_BATCH_SIZE = _env_int("SOLR_BATCH_SIZE", 100)

# Retry / Backoff
MAX_ATTEMPTS          = _env_int("MAX_ATTEMPTS", 5)
BACKOFF_BASE_SECONDS  = _env_int("BACKOFF_BASE_SECONDS", 30)
BACKOFF_MAX_SECONDS   = _env_int("BACKOFF_MAX_SECONDS", 3600)
CLAIM_TIMEOUT_SECONDS = _env_int("CLAIM_TIMEOUT_SECONDS", 300)

# Rules cache
RULES_CACHE_TTL_SECONDS = _env_int("RULES_CACHE_TTL_SECONDS", 60)

# Logging
LOG_LEVEL                  = _env("LOG_LEVEL", "INFO")
LOG_ROTATION               = _env("LOG_ROTATION", "daily")
HEARTBEAT_INTERVAL_SECONDS = _env_int("HEARTBEAT_INTERVAL_SECONDS", 60)


# ---------------------------------------------------------------------------
# 시작 시 검증
# ---------------------------------------------------------------------------

_REQUIRED_ALWAYS = ["RDS_HOST", "RDS_USER", "RDS_PASSWORD", "RDS_DB"]
_REQUIRED_TUNNEL = ["TUNNEL_SSH_HOST", "TUNNEL_SSH_KEY_PATH"]
_REQUIRED_SOLR   = ["SOLR_URL"]


def validate() -> None:
    """
    필수 환경변수를 일괄 검증한다.
    누락 항목이 있으면 목록을 stderr 에 출력하고 sys.exit(1).
    __main__.py 에서 워커 루프 진입 전에 호출한다.
    """
    missing = [k for k in _REQUIRED_ALWAYS if not os.getenv(k)]

    if TUNNEL_ENABLED:
        missing += [k for k in _REQUIRED_TUNNEL if not os.getenv(k)]

    if SINK_TYPE == "solr":
        missing += [k for k in _REQUIRED_SOLR if not os.getenv(k)]

    if not missing:
        return

    print("ERROR: 다음 필수 환경변수가 설정되지 않았습니다:", file=sys.stderr)
    for key in missing:
        print(f"  - {key}", file=sys.stderr)
    print("  .env 파일 또는 환경변수를 확인하세요.", file=sys.stderr)
    sys.exit(1)
