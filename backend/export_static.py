"""
GitHub Pages 정적 배포용 JSON 데이터 생성 스크립트
- 모든 크롤러(run_all_crawlers)를 실행해 SQLite에 저장한 뒤
- 해외 IP 차단 등으로 실패한 소스가 있을 경우 기존 programs.json의 해당 소스 유효 레코드를 보전하며
- frontend/public/data/programs.json 및 frontend/public/data/stats.json 파일을 생성합니다.
"""
import asyncio
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import sys
from typing import Dict, List, Any

KST = timezone(timedelta(hours=9))
BACKEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = BACKEND_DIR.parent
OUT_DIR = ROOT_DIR / "frontend" / "public" / "data"

from database import init_db, query_programs, get_library_stats, get_crawler_logs, upsert_programs  # noqa: E402
from crawlers.manager import run_all_crawlers  # noqa: E402
from crawlers.normalizer import check_is_expired  # noqa: E402
from models import Program  # noqa: E402


def _load_baseline_by_source() -> Dict[str, List[Dict[str, Any]]]:
    progs_path = OUT_DIR / "programs.json"
    if not progs_path.exists():
        return {}
    try:
        data = json.loads(progs_path.read_text(encoding="utf-8"))
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for row in data.get("programs", []):
            src = row.get("source")
            if src:
                grouped.setdefault(src, []).append(row)
        return grouped
    except Exception as e:
        print(f"[Export Static] Failed to load baseline programs.json: {e}")
        return {}


def _restore_failed_sources(summary: Dict[str, Any], baseline: Dict[str, List[Dict[str, Any]]]) -> List[str]:
    restored: List[str] = []
    to_restore: List[Program] = []
    for key, info in summary.items():
        if not isinstance(info, dict):
            continue
        source_name = key.upper()
        if info.get("status") != "OK" or info.get("count", 0) == 0:
            prev_rows = baseline.get(source_name, [])
            if prev_rows:
                for r in prev_rows:
                    expired = check_is_expired(
                        r.get("event_start"),
                        r.get("event_end"),
                        r.get("apply_start"),
                        r.get("apply_end"),
                        r.get("status", "APPLY"),
                        r.get("title", ""),
                    )
                    r_copy = dict(r)
                    if expired:
                        r_copy["is_expired"] = True
                        r_copy["is_new"] = False
                        r_copy["status"] = "CLOSED"
                        r_copy["status_label"] = "마감"
                    r_copy.pop("created_at", None)
                    r_copy.pop("updated_at", None)
                    to_restore.append(Program(**r_copy))
                restored.append(f"{source_name}({len(prev_rows)})")
    if to_restore:
        upsert_programs(to_restore)
    return restored


async def export_static_data() -> int:
    baseline = _load_baseline_by_source()
    init_db()
    summary = await run_all_crawlers()

    restored = _restore_failed_sources(summary, baseline)
    if restored:
        print(f"[Export Static] Preserved baseline rows for failed/blocked sources: {', '.join(restored)}")

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
        "restored_sources": restored,
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
