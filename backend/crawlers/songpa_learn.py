"""
송파구청 교육포털 '송파런'(www.songpa.go.kr/learn/) 유아/어린이/가족 강좌 크롤러
- 송파구 원어민 영어캠프(위례교육센터 포함), 송파런 교육센터, 송파진로체험지원센터, 자치회관 어린이 강좌 수집
"""
from datetime import datetime
import re
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup
import httpx

from models import Program
from crawlers.normalizer import (
    check_is_expired,
    check_is_new,
    classify_day_type,
    classify_target_age,
    determine_status,
    is_kids_program,
)

BASE_URL = "https://www.songpa.go.kr"
LIST_URL = f"{BASE_URL}/learn/youth/program/lecture_list.do"
VIEW_URL = f"{BASE_URL}/learn/youth/program/lecture_view.do"

TARGET_CODES = [
    ("27", "유아"),
    ("28", "어린이"),
    ("35", "가족"),
]


def _normalize_yy_date(date_str: str) -> Optional[str]:
    """'26-12-29' 또는 '2026-12-29' 형태를 'YYYY-MM-DD'로 정규화합니다."""
    m = re.search(r"(\d{2,4})[.\-](\d{1,2})[.\-](\d{1,2})", date_str or "")
    if not m:
        return None
    y = int(m.group(1))
    if y < 100:
        y += 2000
    return f"{y:04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def _extract_period(text: str) -> Tuple[Optional[str], Optional[str]]:
    if not text:
        return None, None
    dates = [_normalize_yy_date(x.group(0)) for x in re.finditer(r"\d{2,4}[.\-]\d{1,2}[.\-]\d{1,2}", text)]
    dates = [d for d in dates if d]
    if len(dates) >= 2:
        return dates[0], dates[1]
    if len(dates) == 1:
        return dates[0], dates[0]
    return None, None


def _friendly_org_name(org: str, title: str) -> str:
    clean_org = " ".join((org or "").replace("/", "").split()).strip()
    if "위례" in title or "위례" in clean_org:
        if "영어캠프" in clean_org or "영어캠프" in title:
            return "위례교육센터(영어캠프)"
        return "위례교육센터(송파런)"
    if "원어민" in clean_org or "원어민 영어캠프" in title:
        return "송파런 영어캠프"
    return clean_org or "송파런 교육포털"


async def fetch_songpa_learn_programs() -> Tuple[List[Program], str, str]:
    """
    반환: (프로그램 목록, 상태코드 [OK / WARNING / SCHEMA_MISMATCH / ERROR], 에러 메시지)
    """
    programs: List[Program] = []
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    status = "OK"
    error_msg = ""
    candidates: Dict[str, Dict] = {}
    today = datetime.now().strftime("%Y-%m-%d")

    async with httpx.AsyncClient(verify=False, timeout=12.0, follow_redirects=True) as client:
        for val8, fallback_target in TARGET_CODES:
            for page in (1, 2):
                try:
                    res = await client.get(
                        LIST_URL,
                        params={"searchVal8": val8, "pageIndex": str(page)},
                        headers=headers,
                    )
                    if res.status_code != 200:
                        status = "WARNING"
                        error_msg = f"송파런 HTTP 상태코드 {res.status_code}"
                        continue

                    soup = BeautifulSoup(res.text, "html.parser")
                    links = soup.select("a.program_link[href*='lecture_idx='], a[href*='lecture_view.do']")
                    if not links:
                        break

                    for a in links:
                        href = a.get("href", "")
                        m_idx = re.search(r"lecture_idx=(\d+)", href)
                        if not m_idx:
                            continue
                        lec_idx = m_idx.group(1)
                        if lec_idx in candidates:
                            continue

                        tit_el = a.select_one(".lec_tit")
                        title = " ".join((tit_el.get_text() if tit_el else a.get_text()).split())
                        if not title:
                            continue

                        loca_el = a.select_one(".loca")
                        org_raw = " ".join(loca_el.get_text().split()) if loca_el else ""

                        desc_i = a.select_one(".desc_box i")
                        info_lines = desc_i.get_text("\n") if desc_i else a.get_text("\n")
                        apply_start = apply_end = event_start = event_end = None
                        for ln in info_lines.splitlines():
                            if "접수기간" in ln:
                                apply_start, apply_end = _extract_period(ln)
                            elif "교육기간" in ln:
                                event_start, event_end = _extract_period(ln)

                        # 성인 취미/스포츠 등 명백한 비어린이 강좌는 상세 요청 전 사전 배제
                        if re.search(r"(성인|요가|필라테스|라인댄스|노래교실|양재|바리스타|네일아트|자격증)", title):
                            continue

                        # 이미 교육기간까지 모두 종료된 과거 강좌(예: 10월 이전 마감)는 상세 요청 생략
                        if event_end and event_end < today and (not apply_end or apply_end < today):
                            continue

                        candidates[lec_idx] = {
                            "lec_idx": lec_idx,
                            "title": title,
                            "org_raw": org_raw,
                            "fallback_target": fallback_target,
                            "apply_start": apply_start,
                            "apply_end": apply_end,
                            "event_start": event_start,
                            "event_end": event_end,
                            "detail_url": f"{VIEW_URL}?lecture_idx={lec_idx}",
                        }
                except Exception as exc:
                    status = "WARNING"
                    error_msg = f"송파런 목록 수집 실패: {exc}"

        for lec_idx, item in candidates.items():
            try:
                det_res = await client.get(item["detail_url"], headers=headers)
                if det_res.status_code != 200:
                    continue
                ds = BeautifulSoup(det_res.text, "html.parser")
                box = ds.select_one("#contents, .sub_con, main") or ds.body
                lines = [" ".join(ln.split()) for ln in box.get_text("\n").splitlines() if ln.strip()]

                raw_status = ""
                for st_kw in ("신청가능", "접수대기", "대기신청", "신청마감", "교육전", "교육중", "교육종료", "접수마감"):
                    if st_kw in lines:
                        raw_status = st_kw
                        break

                meta: Dict[str, str] = {}
                labels = ("교육기관", "교육분야", "교육대상", "교육기간", "교육시간", "수강료", "정원", "모집정원", "장소", "교육장소")
                for i, ln in enumerate(lines):
                    clean_lbl = ln.rstrip(" :").strip()
                    if clean_lbl in labels and i + 1 < len(lines):
                        val = lines[i + 1]
                        if val.rstrip(" :").strip() not in labels:
                            meta[clean_lbl] = val

                target_raw = meta.get("교육대상") or item["fallback_target"]
                title = item["title"]

                if not is_kids_program(target_raw, title):
                    continue
                target_age_group, target_label = classify_target_age(target_raw, title)
                if target_age_group == "EXCLUDE":
                    continue

                apply_start = item["apply_start"]
                apply_end = item["apply_end"]
                event_start = item["event_start"]
                event_end = item["event_end"]
                if not event_start and meta.get("교육기간"):
                    event_start, event_end = _extract_period(meta["교육기간"])

                dt_start = dt_end = None
                try:
                    if apply_start:
                        dt_start = datetime.strptime(f"{apply_start} 00:00", "%Y-%m-%d %H:%M")
                    if apply_end:
                        dt_end = datetime.strptime(f"{apply_end} 23:59", "%Y-%m-%d %H:%M")
                except Exception:
                    pass

                if raw_status == "신청가능":
                    prog_status = "APPLY"
                elif raw_status in ("접수대기", "교육전"):
                    prog_status = "READY"
                elif raw_status == "대기신청":
                    prog_status = "WAIT"
                elif raw_status in ("신청마감", "접수마감", "교육종료"):
                    prog_status = "CLOSED"
                else:
                    prog_status = determine_status(raw_status, dt_start, dt_end)

                event_time_info = meta.get("교육시간", "")
                day_type, day_label = classify_day_type(event_time_info, event_start, event_end, title)
                is_expired = check_is_expired(event_start, event_end, apply_start, apply_end, prog_status, title=title)
                if is_expired and prog_status == "CLOSED":
                    continue
                is_new = check_is_new(apply_start, prog_status, title, is_expired)

                org_name = _friendly_org_name(meta.get("교육기관") or item["org_raw"], title)
                fee = meta.get("수강료") or "송파런 확인"
                capacity = meta.get("정원") or meta.get("모집정원") or "정원제"
                location = meta.get("교육장소") or meta.get("장소") or org_name

                status_labels = {
                    "APPLY": "접수중",
                    "READY": "접수예정",
                    "WAIT": "대기접수",
                    "CLOSED": "마감",
                }

                programs.append(
                    Program(
                        id=f"songpa_learn_{lec_idx}",
                        source="SONGPA_LEARN",
                        library_name=org_name,
                        region="송파",
                        title=title,
                        target_age_group=target_age_group,
                        target_label=target_label,
                        target_raw=target_raw,
                        day_type=day_type,
                        day_label=day_label,
                        is_new=is_new,
                        is_expired=is_expired,
                        fee=fee,
                        capacity=capacity,
                        apply_start=f"{apply_start} 10:00" if apply_start else None,
                        apply_end=f"{apply_end} 18:00" if apply_end else None,
                        event_start=event_start,
                        event_end=event_end,
                        event_time_info=event_time_info,
                        location=location,
                        status=prog_status,
                        status_label=status_labels.get(prog_status, "접수중"),
                        detail_url=item["detail_url"],
                        apply_url=item["detail_url"],
                    )
                )
            except Exception:
                continue

    return programs, status, error_msg
