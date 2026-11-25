"""
GitHub Pages 정적 배포용 JSON 데이터 생성 스크립트
- 모든 크롤러(run_all_crawlers)를 실행해 SQLite에 저장한 뒤
- frontend/public/data/programs.json 및 frontend/public/data/stats.json 파일을 생성합니다.
"""
import asyncio
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import sys

KST = timezone(timedelta(hours=9))
BACKEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = BACKEND_DIR.parent
OUT_DIR = ROOT_DIR / "frontend" / "public" / "data"

from database import init_db, query_programs, get_library_stats, get_crawler_logs  # noqa: E402
from crawlers.manager import run_all_crawlers  # noqa: E402


async def export_static_data() -> int:
    init_db()
    summary = await run_all_crawlers()

    all_programs = query_programs(include_expired=True)
    active_programs = [p for p in all_programs if not p.get("is_expired") and p.get("status") != "CLOSED"]

    now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")

    stats_payload = {
        "generated_at": now_kst,
        "total": len(all_programs),
        "active_total": len(active_programs),
        "new_count": sum(1 for p in active_programs if p.get("is_new")),
        "expired_count": len(all_programs) - len(active_programs),
        "preschool_count": sum(1 for p in active_programs if p.get("target_age_group") == "PRESCHOOL"),
        "infant_count": sum(1 for p in active_programs if p.get("target_age_group") == "INFANT"),
        "elementary_count": sum(1 for p in active_programs if p.get("target_age_group") == "ELEMENTARY"),
        "family_count": sum(1 for p in active_programs if p.get("target_age_group") == "FAMILY"),
        "all_age_count": sum(1 for p in active_programs if p.get("target_age_group") in ("ALL", "FAMILY")),
        "apply_count": sum(1 for p in active_programs if p.get("status") == "APPLY"),
        "ready_count": sum(1 for p in active_programs if p.get("status") == "READY"),
        "weekend_count": sum(1 for p in active_programs if p.get("day_type") == "WEEKEND"),
        "weekday_count": sum(1 for p in active_programs if p.get("day_type") == "WEEKDAY"),
        "library_stats": get_library_stats(),
        "crawler_logs": get_crawler_logs(),
        "crawl_summary": summary,
    }

    programs_payload = {
        "generated_at": now_kst,
        "count": len(all_programs),
        "programs": all_programs,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "programs.json").write_text(
        json.dumps(programs_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OUT_DIR / "stats.json").write_text(
        json.dumps(stats_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"[Export Static] Generated {OUT_DIR / 'programs.json'} ({len(all_programs)} total, {len(active_programs)} active)")
    ok_sources = sum(1 for k, v in summary.items() if isinstance(v, dict) and v.get("status") == "OK")
    print(f"[Export Static] Crawler OK sources: {ok_sources}/5, summary={summary}")
    if len(active_programs) == 0:
        print("[Export Static] ERROR: Zero active programs exported!", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(export_static_data()))
