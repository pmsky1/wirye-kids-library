import asyncio
from typing import List, Dict, Any
from models import Program
from database import upsert_programs, record_crawler_log, expire_missing_programs
from crawlers.songpa import fetch_songpa_programs
from crawlers.songpa_learn import fetch_songpa_learn_programs
from crawlers.hanam import fetch_hanam_programs
from crawlers.seongnam import fetch_seongnam_programs
from crawlers.experience import fetch_experience_programs


async def run_all_crawlers() -> Dict[str, Any]:
    """
    송파구립 13개 도서관, 송파런, 하남위례, 성남위례, 체험관 및 송파소식 크롤러를 비동기 병렬로 실행하여
    결과를 정규화하고 DB 및 상태 로그에 저장합니다.
    """
    print("[Crawler Manager] Starting crawls for Songpa, SongpaLearn, Hanam, Seongnam, and Experience...")

    results = await asyncio.gather(
        fetch_songpa_programs(),
        fetch_songpa_learn_programs(),
        fetch_hanam_programs(),
        fetch_seongnam_programs(),
        fetch_experience_programs(),
        return_exceptions=True
    )

    all_programs: List[Program] = []
    summary = {}

    sources = [
        ("SONGPA", "송파구 통합도서관 (13개관 및 무료영화)"),
        ("SONGPA_LEARN", "송파런 (원어민캠프 및 자치회관 강좌)"),
        ("HANAM", "하남시립 위례도서관"),
        ("SEONGNAM", "성남시립 위례도서관"),
        ("EXPERIENCE", "송파어린이문화회관 및 송파소식 행사"),
    ]

    for i, (source_key, lib_name) in enumerate(sources):
        res = results[i]
        if isinstance(res, Exception):
            print(f"[Crawler Manager] {source_key} crashed with exception: {res}")
            record_crawler_log(source_key, lib_name, "ERROR", 0, str(res))
            summary[source_key.lower()] = {"count": 0, "status": "ERROR", "error": str(res)}
        else:
            progs, status, err_msg = res
            print(f"[Crawler Manager] {source_key} finished: {len(progs)} items, status={status}")
            record_crawler_log(source_key, lib_name, status, len(progs), err_msg)
            all_programs.extend(progs)
            summary[source_key.lower()] = {"count": len(progs), "status": status, "error": err_msg}

    if all_programs:
        upsert_programs(all_programs)

    # 정상(OK)으로 수집 완료된 소스는 이번 결과에 없는 기존 활성 레코드를 마감/만료 정리
    for i, (source_key, _) in enumerate(sources):
        res = results[i]
        if not isinstance(res, Exception):
            progs, status, _ = res
            if status == "OK" and progs:
                expire_missing_programs(source_key, [p.id for p in progs])

    summary["total"] = len(all_programs)
    return summary
