import httpx
from bs4 import BeautifulSoup
import re
from typing import List, Tuple
from models import Program
from crawlers.normalizer import classify_target_age, determine_status, classify_day_type, check_is_expired, check_is_new, is_kids_program
from datetime import datetime

BASE_URL = "https://www.hanamlib.go.kr"
LIST_URL = f"{BASE_URL}/wilib/selectWebEdcLctreList.do"


async def fetch_hanam_programs() -> Tuple[List[Program], str, str]:
    """
    반환: (프로그램 목록, 상태코드 [OK / WARNING / SCHEMA_MISMATCH / ERROR], 에러 메시지)
    """
    programs: List[Program] = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    status = "OK"
    error_msg = ""

    async with httpx.AsyncClient(verify=False, timeout=12.0) as client:
        try:
            found_any = False
            for page in [1, 2]:
                params = {
                    "key": "975",
                    "pageIndex": page,
                    "pageUnit": "10",
                    "searchCnd": "all"
                }
                try:
                    res = await client.get(LIST_URL, params=params, headers=headers)
                except Exception as net_err:
                    status = "WARNING"
                    error_msg = f"하남 연결 실패: {net_err}"
                    continue

                if res.status_code != 200:
                    status = "WARNING"
                    error_msg = f"하남 HTTP 응답코드 {res.status_code}"
                    continue

                soup = BeautifulSoup(res.text, "html.parser")
                # 폴백 선택자: p-table, table, bbs_list 등
                rows = soup.select("table.p-table tbody tr, table.table tbody tr, table tbody tr, .bbs_list li")
                if not rows:
                    break

                for row in rows:
                    try:
                        tds = row.find_all("td")
                        if len(tds) < 4:
                            continue

                        a_tag = row.find("a")
                        if not a_tag:
                            continue

                        title = a_tag.text.strip()
                        href = a_tag.get("href", "")
                        match_no = re.search(r"edcLctreNo=(\d+)", href)
                        if not match_no:
                            continue
                        lctre_no = match_no.group(1)
                        program_id = f"hanam_{lctre_no}"
                        found_any = True

                        raw_target = ""
                        if len(tds) >= 2:
                            raw_target = tds[1].text.strip()
                        title_target_match = re.search(r"<([^>]+)>", title)
                        if title_target_match:
                            raw_target = f"{raw_target} {title_target_match.group(1)}"

                        if not is_kids_program(raw_target, title):
                            continue

                        target_age_group, target_label = classify_target_age(raw_target, title)
                        if target_age_group == "EXCLUDE":
                            continue

                        event_period = ""
                        apply_period = ""
                        capacity = ""
                        raw_status = ""

                        for td in tds:
                            txt = td.text.strip()
                            if re.search(r'\d{4}-\d{2}-\d{2}', txt) and "~" in txt:
                                if ":" in txt and not apply_period:
                                    apply_period = txt
                                elif not event_period:
                                    event_period = txt
                            elif any(k in txt for k in ["교육중", "접수중", "접수마감", "접수대기", "마감", "종료"]):
                                raw_status = txt
                            elif "/" in txt and not capacity:
                                capacity = txt

                        apply_start = None
                        apply_end = None
                        if apply_period and "~" in apply_period:
                            parts = apply_period.split("~")
                            apply_start = parts[0].strip()
                            apply_end = parts[1].strip()

                        event_start = None
                        event_end = None
                        if event_period and "~" in event_period:
                            eparts = event_period.split("~")
                            event_start = eparts[0].strip()
                            event_end = eparts[1].strip()
                        elif event_period:
                            event_start = event_period
                            event_end = event_period

                        dt_start = None
                        dt_end = None
                        try:
                            if apply_start:
                                dt_start = datetime.strptime(apply_start, "%Y-%m-%d %H:%M")
                            if apply_end:
                                dt_end = datetime.strptime(apply_end, "%Y-%m-%d %H:%M")
                        except Exception:
                            pass

                        prog_status = determine_status(raw_status, dt_start, dt_end)
                        day_type, day_label = classify_day_type("", event_start, event_end, title)
                        is_expired = check_is_expired(event_start, event_end, apply_start, apply_end, prog_status)
                        is_new = check_is_new(apply_start, prog_status, title, is_expired)

                        status_labels = {
                            "APPLY": "접수중",
                            "READY": "접수예정",
                            "WAIT": "대기접수",
                            "CLOSED": "마감"
                        }

                        detail_url = f"{BASE_URL}/wilib/selectWebEdcLctreView.do?key=975&edcLctreNo={lctre_no}"

                        programs.append(Program(
                            id=program_id,
                            source="HANAM",
                            library_name="하남위례도서관",
                            region="하남",
                            title=title,
                            target_age_group=target_age_group,
                            target_label=target_label,
                            target_raw=raw_target.strip(),
                            day_type=day_type,
                            day_label=day_label,
                            is_new=is_new,
                            is_expired=is_expired,
                            fee="무료",
                            capacity=capacity,
                            apply_start=apply_start,
                            apply_end=apply_end,
                            event_start=event_start,
                            event_end=event_end,
                            event_time_info="",
                            location="하남위례도서관 강의실",
                            status=prog_status,
                            status_label=status_labels.get(prog_status, "접수중"),
                            detail_url=detail_url,
                            apply_url=detail_url
                        ))
                    except Exception:
                        continue

            if not found_any and status == "OK":
                status = "SCHEMA_MISMATCH"
                error_msg = "하남위례도서관 수강신청 목록 구조 변경 감지"

        except Exception as e:
            status = "ERROR"
            error_msg = f"하남 크롤러 전역 에러: {e}"

    return programs, status, error_msg
