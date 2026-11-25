import sqlite3
import os
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from models import Program
from crawlers.normalizer import check_is_expired, matches_age_filter

DB_PATH = os.path.join(os.path.dirname(__file__), "wirye_kids.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS programs (
        id TEXT PRIMARY KEY,
        source TEXT NOT NULL,
        library_name TEXT NOT NULL,
        region TEXT NOT NULL,
        title TEXT NOT NULL,
        target_age_group TEXT NOT NULL,
        target_label TEXT NOT NULL,
        target_raw TEXT,
        day_type TEXT DEFAULT 'ALL',
        day_label TEXT DEFAULT '상시/미정',
        is_new INTEGER DEFAULT 0,
        is_expired INTEGER DEFAULT 0,
        fee TEXT DEFAULT '무료',
        capacity TEXT,
        apply_start TEXT,
        apply_end TEXT,
        event_start TEXT,
        event_end TEXT,
        event_time_info TEXT,
        location TEXT,
        status TEXT NOT NULL,
        status_label TEXT NOT NULL,
        detail_url TEXT NOT NULL,
        apply_url TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 마이그레이션: 기존 컬럼 누락 시 자동 추가
    for col, ctype, cdef in [
        ("day_type", "TEXT", "'ALL'"),
        ("day_label", "TEXT", "'상시/미정'"),
        ("is_new", "INTEGER", "0"),
        ("is_expired", "INTEGER", "0")
    ]:
        try:
            cursor.execute(f"ALTER TABLE programs ADD COLUMN {col} {ctype} DEFAULT {cdef}")
        except Exception:
            pass

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_target ON programs(target_age_group);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON programs(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_region ON programs(region);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_library ON programs(library_name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_day_type ON programs(day_type);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_is_new ON programs(is_new);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_is_expired ON programs(is_expired);")

    # 크롤러 수집 상태 및 사이트 개편 감지용 로그 테이블
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS crawler_logs (
        source TEXT PRIMARY KEY,
        library_name TEXT NOT NULL,
        last_attempt_at TEXT NOT NULL,
        last_success_at TEXT,
        status TEXT NOT NULL,
        item_count INTEGER DEFAULT 0,
        error_message TEXT
    );
    """)
    conn.commit()
    conn.close()


def record_crawler_log(source: str, library_name: str, status: str, item_count: int, error_message: Optional[str] = None):
    conn = get_db()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
    INSERT INTO crawler_logs (source, library_name, last_attempt_at, last_success_at, status, item_count, error_message)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(source) DO UPDATE SET
        last_attempt_at=excluded.last_attempt_at,
        last_success_at=CASE WHEN excluded.status IN ('OK', 'WARNING') THEN excluded.last_attempt_at ELSE crawler_logs.last_success_at END,
        status=excluded.status,
        item_count=excluded.item_count,
        error_message=excluded.error_message
    """, (
        source, library_name, now_str,
        now_str if status in ('OK', 'WARNING') else None,
        status, item_count, error_message
    ))
    conn.commit()
    conn.close()


def get_crawler_logs() -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM crawler_logs ORDER BY source ASC")
    rows = cursor.fetchall()
    results = [dict(r) for r in rows]
    conn.close()
    return results


def upsert_programs(programs: List[Program]):
    conn = get_db()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for p in programs:
        cursor.execute("""
        INSERT INTO programs (
            id, source, library_name, region, title, target_age_group, target_label,
            target_raw, day_type, day_label, is_new, is_expired, fee, capacity,
            apply_start, apply_end, event_start, event_end,
            event_time_info, location, status, status_label, detail_url, apply_url,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            library_name=excluded.library_name,
            region=excluded.region,
            title=excluded.title,
            target_age_group=excluded.target_age_group,
            target_label=excluded.target_label,
            target_raw=excluded.target_raw,
            day_type=excluded.day_type,
            day_label=excluded.day_label,
            is_new=excluded.is_new,
            is_expired=excluded.is_expired,
            fee=excluded.fee,
            capacity=excluded.capacity,
            apply_start=excluded.apply_start,
            apply_end=excluded.apply_end,
            event_start=excluded.event_start,
            event_end=excluded.event_end,
            event_time_info=excluded.event_time_info,
            location=excluded.location,
            status=excluded.status,
            status_label=excluded.status_label,
            detail_url=excluded.detail_url,
            apply_url=excluded.apply_url,
            updated_at=excluded.updated_at
        """, (
            p.id, p.source, p.library_name, p.region, p.title, p.target_age_group, p.target_label,
            p.target_raw, p.day_type, p.day_label, 1 if p.is_new else 0, 1 if p.is_expired else 0,
            p.fee, p.capacity, p.apply_start, p.apply_end, p.event_start, p.event_end,
            p.event_time_info, p.location, p.status, p.status_label, p.detail_url, p.apply_url,
            now_str, now_str
        ))
    conn.commit()
    conn.close()


def expire_missing_programs(source: str, collected_ids: List[str]):
    """
    정상 크롤링이 완료된 소스에 대해 이번 수집 결과에 더 이상 존재하지 않는
    과거 활성 레코드(게시판에서 밀려나거나 제외된 공고)를 만료 처리해 좀비 노출을 방지합니다.
    """
    if not collected_ids:
        return
    conn = get_db()
    cursor = conn.cursor()
    placeholders = ",".join("?" for _ in collected_ids)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        f"""
        UPDATE programs
        SET is_expired = 1,
            is_new = 0,
            status = 'CLOSED',
            status_label = '마감',
            updated_at = ?
        WHERE source = ?
          AND id NOT IN ({placeholders})
          AND (is_expired = 0 OR status != 'CLOSED')
        """,
        [now_str, source, *collected_ids],
    )
    conn.commit()
    conn.close()


def _is_apply_ended(apply_end: Optional[str], now: datetime) -> bool:
    """실시간 현재 시각 기준 접수 마감일이 지났는지 확인합니다."""
    if not apply_end:
        return False
    val = apply_end.strip()
    if len(val) >= 16:
        try:
            return now > datetime.strptime(val[:16], "%Y-%m-%d %H:%M")
        except ValueError:
            pass
    if len(val) >= 10:
        return val[:10] < now.strftime("%Y-%m-%d")
    return False


def _refresh_realtime_flags(item: Dict[str, Any], now: datetime) -> Dict[str, Any]:
    """
    크롤링 주기 사이에 날짜/시각이 경과해도 조회 시점에 정확한 상태/만료 여부를 반영합니다.
    """
    apply_ended = _is_apply_ended(item.get("apply_end"), now)
    if apply_ended and item.get("status") != "CLOSED":
        item["status"] = "CLOSED"
        item["status_label"] = "마감"

    if not item.get("is_expired"):
        expired = check_is_expired(
            item.get("event_start"),
            item.get("event_end"),
            item.get("apply_start"),
            item.get("apply_end"),
            item.get("status", "APPLY"),
            title=item.get("title", ""),
        )
        if expired:
            item["is_expired"] = 1
            item["is_new"] = 0
    return item


def query_programs(
    region: Optional[str] = None,
    library: Optional[str] = None,
    age_group: Optional[str] = None,
    day_type: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    include_expired: bool = False
) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()

    conditions = []
    params = []

    if region and region != "ALL":
        conditions.append("region = ?")
        params.append(region)

    if library and library != "ALL":
        conditions.append("library_name = ?")
        params.append(library)

    if day_type and day_type != "ALL":
        conditions.append("day_type = ?")
        params.append(day_type)

    if search:
        conditions.append("(title LIKE ? OR target_raw LIKE ? OR location LIKE ?)")
        search_param = f"%{search}%"
        params.extend([search_param, search_param, search_param])

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # 정렬 순서:
    # 1. ⚡ 접수 상태 최우선: 접수중(APPLY) -> 접수예정(READY) -> 대기(WAIT) -> 마감(CLOSED)
    # 2. ✨ 신규 업데이트 강좌(is_new = 1) 우선 노출
    # 3. 🎉 주말(WEEKEND) 우선
    # 4. 신청 시작일시 오름차순
    query = f"""
    SELECT * FROM programs
    {where_clause}
    ORDER BY 
        CASE status 
            WHEN 'APPLY' THEN 1 
            WHEN 'READY' THEN 2 
            WHEN 'WAIT' THEN 3 
            ELSE 4 
        END,
        is_new DESC,
        CASE day_type
            WHEN 'WEEKEND' THEN 1
            ELSE 2
        END,
        apply_start ASC,
        id DESC
    """

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    now = datetime.now()
    results: List[Dict[str, Any]] = []
    for r in rows:
        item = _refresh_realtime_flags(dict(r), now)
        if not include_expired:
            if item.get("is_expired"):
                continue
            if status != "CLOSED" and item.get("status") == "CLOSED":
                continue
        if status and status != "ALL" and item.get("status") != status:
            continue
        if age_group and age_group != "ALL":
            if not matches_age_filter(
                item.get("target_age_group", ""),
                age_group,
                item.get("target_raw") or "",
                item.get("title") or "",
            ):
                continue
        results.append(item)

    status_rank = {"APPLY": 1, "READY": 2, "WAIT": 3}
    results.sort(
        key=lambda x: (
            status_rank.get(x.get("status", ""), 4),
            -(1 if x.get("is_new") else 0),
            1 if x.get("day_type") == "WEEKEND" else 2,
            x.get("apply_start") or "9999-99-99",
            x.get("id", ""),
        )
    )
    return results


def get_library_stats():
    all_rows = query_programs(include_expired=True)
    grouped: Dict[tuple, Dict[str, Any]] = {}
    for p in all_rows:
        key = (p["region"], p["library_name"])
        if key not in grouped:
            grouped[key] = {
                "region": p["region"],
                "library_name": p["library_name"],
                "total_count": 0,
                "active_count": 0,
                "new_count": 0,
                "apply_count": 0,
                "ready_count": 0,
                "preschool_count": 0,
                "weekend_count": 0,
            }
        g = grouped[key]
        g["total_count"] += 1
        is_active = (not p.get("is_expired")) and (p.get("status") != "CLOSED")
        if is_active:
            g["active_count"] += 1
            if p.get("is_new"):
                g["new_count"] += 1
            if p.get("status") == "APPLY":
                g["apply_count"] += 1
            elif p.get("status") == "READY":
                g["ready_count"] += 1
            if p.get("target_age_group") == "PRESCHOOL":
                g["preschool_count"] += 1
            if p.get("day_type") == "WEEKEND":
                g["weekend_count"] += 1

    return sorted(grouped.values(), key=lambda x: (x["region"], x["library_name"]))
