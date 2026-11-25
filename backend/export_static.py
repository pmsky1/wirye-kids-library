"""
GitHub Pages 정적 배포용 JSON 데이터 생성 및 안전 Git 동기화 모듈
- run_all_crawlers 결과를 frontend/public/data/programs.json 및 stats.json으로 내보냅니다.
- 해외 IP 차단 등으로 실패한 소스가 있으면 직전 baseline 데이터를 보전합니다.
- 로컬 서버에서는 실제 데이터 변동 시에만 data/*.json 2개 파일만 안전하게 커밋(--only) 후 GitHub에 push합니다.
"""
import asyncio
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import subprocess
import sys
from typing import Dict, List, Any, Optional, Tuple

KST = timezone(timedelta(hours=9))
BACKEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = BACKEND_DIR.parent
OUT_DIR = ROOT_DIR / "frontend" / "public" / "data"
DATA_REL_PATHS = [
    "frontend/public/data/programs.json",
    "frontend/public/data/stats.json",
]

from database import init_db, query_programs, get_library_stats, get_crawler_logs, upsert_programs, seed_baseline_programs  # noqa: E402
from crawlers.manager import run_all_crawlers  # noqa: E402
from crawlers.normalizer import check_is_expired, check_is_new  # noqa: E402
from models import Program  # noqa: E402

_sync_lock = asyncio.Lock()
_last_sync_info: Dict[str, Any] = {
    "status": "IDLE",
    "message": "대기중",
    "last_synced_at": None,
    "commit": None,
}


def get_last_sync_info() -> Dict[str, Any]:
    return dict(_last_sync_info)


def should_auto_sync_on_startup(min_age_minutes: int = 30) -> bool:
    """--reload로 백엔드가 재시작될 때 매번 크롤링+푸시하지 않도록 직전 생성 시각 기준 쿨다운을 확인합니다."""
    stats_path = OUT_DIR / "stats.json"
    if not stats_path.exists():
        return True
    try:
        data = json.loads(stats_path.read_text(encoding="utf-8"))
        gen_str = (data.get("generated_at") or "").replace(" KST", "").strip()
        if not gen_str:
            return True
        gen_dt = datetime.strptime(gen_str, "%Y-%m-%d %H:%M").replace(tzinfo=KST)
        age = (datetime.now(KST) - gen_dt).total_seconds()
        return age >= min_age_minutes * 60
    except Exception:
        return True


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


def _load_baseline_logs() -> Dict[str, Dict[str, Any]]:
    stats_path = OUT_DIR / "stats.json"
    if not stats_path.exists():
        return {}
    try:
        data = json.loads(stats_path.read_text(encoding="utf-8"))
        return {log["source"]: log for log in data.get("crawler_logs", []) if log.get("source")}
    except Exception:
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
                    else:
                        r_copy["is_new"] = check_is_new(
                            r_copy.get("apply_start"),
                            r_copy.get("status", "APPLY"),
                            r_copy.get("title", ""),
                            is_expired=False,
                            first_seen_at=r.get("created_at"),
                        )
                    r_copy.pop("created_at", None)
                    r_copy.pop("updated_at", None)
                    to_restore.append(Program(**r_copy))
                restored.append(f"{source_name}({len(prev_rows)})")
    if to_restore:
        upsert_programs(to_restore)
    return restored


def _merge_logs_with_baseline(
    current_logs: List[Dict[str, Any]],
    baseline_logs: Dict[str, Dict[str, Any]],
    restored: List[str],
) -> List[Dict[str, Any]]:
    restored_sources = {item.split("(", 1)[0] for item in restored}
    merged: List[Dict[str, Any]] = []
    for log in current_logs:
        src = log.get("source")
        if src in restored_sources and src in baseline_logs:
            prev = dict(baseline_logs[src])
            prev["status"] = "WARNING"
            prev["error_message"] = "원격 환경 미지원으로 직전 로컬 수집 데이터를 유지 중입니다."
            merged.append(prev)
        else:
            merged.append(log)
    return merged


def write_static_files(
    summary: Optional[Dict[str, Any]] = None,
    restored: Optional[List[str]] = None,
    baseline_logs: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Tuple[Dict[str, Any], bool]:
    """현재 SQLite DB 상태를 읽어 programs.json 및 stats.json을 갱신하고 실제 내용 변경 여부를 반환합니다."""
    all_programs = query_programs(include_expired=True)
    active_programs = [p for p in all_programs if not p.get("is_expired") and p.get("status") != "CLOSED"]
    now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")

    raw_logs = get_crawler_logs()
    crawler_logs = (
        _merge_logs_with_baseline(raw_logs, baseline_logs or {}, restored or [])
        if restored
        else raw_logs
    )

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
        "crawler_logs": crawler_logs,
        "crawl_summary": summary or {},
        "restored_sources": restored or [],
    }

    programs_payload = {
        "generated_at": now_kst,
        "count": len(all_programs),
        "programs": all_programs,
    }

    def _canonical_programs(obj: Dict[str, Any]) -> str:
        cleaned = []
        for row in obj.get("programs", []):
            r = {k: v for k, v in row.items() if k not in ("created_at", "updated_at")}
            cleaned.append(r)
        return json.dumps(cleaned, ensure_ascii=False, sort_keys=True)

    prev_progs_path = OUT_DIR / "programs.json"
    data_changed = True
    if prev_progs_path.exists():
        try:
            prev_obj = json.loads(prev_progs_path.read_text(encoding="utf-8"))
            if _canonical_programs(prev_obj) == _canonical_programs(programs_payload):
                data_changed = False
        except Exception:
            data_changed = True

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if data_changed or not (OUT_DIR / "stats.json").exists():
        (OUT_DIR / "programs.json").write_text(
            json.dumps(programs_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (OUT_DIR / "stats.json").write_text(
            json.dumps(stats_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return stats_payload, data_changed


def _run_git(args: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        timeout=60,
    )


def _commit_and_push_static_sync(reason: str) -> Dict[str, Any]:
    """다른 작업 파일을 건드리지 않고 programs.json, stats.json만 커밋 및 푸시합니다."""
    if not (ROOT_DIR / ".git").exists():
        return {"status": "ERROR", "message": "Git 저장소가 초기화되어 있지 않습니다."}

    status_res = _run_git(["status", "--porcelain", "--", *DATA_REL_PATHS])
    if status_res.returncode != 0:
        return {"status": "ERROR", "message": f"Git 상태 확인 실패: {status_res.stderr.strip()}"}

    if not status_res.stdout.strip():
        return {
            "status": "NO_CHANGES",
            "message": "이미 최신 데이터가 GitHub에 반영되어 있습니다.",
        }

    add_res = _run_git(["add", "--", *DATA_REL_PATHS])
    if add_res.returncode != 0:
        return {"status": "ERROR", "message": f"Git add 실패: {add_res.stderr.strip()}"}

    now_label = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    commit_msg = f"chore(data): sync WiKids data ({reason}, {now_label} KST)"
    commit_res = _run_git(["commit", "--only", *DATA_REL_PATHS, "-m", commit_msg])
    if commit_res.returncode != 0:
        err = commit_res.stderr.strip() or commit_res.stdout.strip()
        if "nothing to commit" in err.lower():
            return {"status": "NO_CHANGES", "message": "이미 최신 데이터가 GitHub에 반영되어 있습니다."}
        return {"status": "ERROR", "message": f"Git commit 실패: {err}"}

    push_res = _run_git(["push", "origin", "main"])
    if push_res.returncode != 0:
        err = push_res.stderr.strip() or push_res.stdout.strip()
        return {"status": "ERROR", "message": f"Git push 실패 (수동 확인 필요): {err}"}

    sha_res = _run_git(["rev-parse", "--short", "HEAD"])
    short_sha = sha_res.stdout.strip() if sha_res.returncode == 0 else ""

    return {
        "status": "PUSHED",
        "commit": short_sha,
        "message": "GitHub 업로드 완료! 약 30초 후 공개 사이트에 반영됩니다.",
    }


async def sync_github_pages(crawl: bool = True, reason: str = "manual") -> Dict[str, Any]:
    """로컬에서 최신 데이터를 수집해 정적 JSON을 갱신하고 변경 시 GitHub에 업로드합니다."""
    global _last_sync_info
    async with _sync_lock:
        baseline = _load_baseline_by_source()
        init_db()
        baseline_rows = [row for rows in baseline.values() for row in rows]
        seed_baseline_programs(baseline_rows)
        summary = None
        if crawl:
            summary = await run_all_crawlers()

        stats_payload, data_changed = write_static_files(summary=summary)
        git_result = await asyncio.to_thread(_commit_and_push_static_sync, reason)

        now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")
        result = {
            **git_result,
            "data_changed": data_changed,
            "active_total": stats_payload.get("active_total"),
            "total": stats_payload.get("total"),
            "generated_at": stats_payload.get("generated_at"),
            "synced_at": now_kst,
            "reason": reason,
        }
        _last_sync_info = result
        print(f"[GitHub Sync] reason={reason}, status={result.get('status')}, active={result.get('active_total')}, msg={result.get('message')}")
        return result


async def export_static_data() -> int:
    """CI/로컬 공용 정적 JSON 생성 진입점 (해외 IP 차단 소스는 기존 데이터를 보전합니다)."""
    baseline = _load_baseline_by_source()
    baseline_logs = _load_baseline_logs()
    init_db()
    baseline_rows = [row for rows in baseline.values() for row in rows]
    seeded = seed_baseline_programs(baseline_rows)
    if seeded:
        print(f"[Export Static] Seeded {seeded} baseline rows (preserving original created_at)")
    summary = await run_all_crawlers()

    restored = _restore_failed_sources(summary, baseline)
    if restored:
        print(f"[Export Static] Preserved baseline rows for failed/blocked sources: {', '.join(restored)}")

    stats_payload, _ = write_static_files(
        summary=summary,
        restored=restored,
        baseline_logs=baseline_logs,
    )

    # export_static CLI 실행 시에는 항상 generated_at을 최신 시각으로 기록
    (OUT_DIR / "stats.json").write_text(
        json.dumps(stats_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    active_total = stats_payload.get("active_total", 0)
    total = stats_payload.get("total", 0)
    print(f"[Export Static] Generated {OUT_DIR / 'programs.json'} ({total} total, {active_total} active)")
    ok_sources = sum(1 for k, v in summary.items() if isinstance(v, dict) and v.get("status") == "OK")
    print(f"[Export Static] Crawler OK sources: {ok_sources}/5, summary={summary}")
    if active_total == 0:
        print("[Export Static] ERROR: Zero active programs exported!", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(export_static_data()))
