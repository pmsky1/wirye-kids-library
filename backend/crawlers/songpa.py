import httpx
from bs4 import BeautifulSoup
import re
from typing import List, Tuple
from models import Program
from crawlers.normalizer import classify_target_age, determine_status, classify_day_type, check_is_expired, check_is_new, is_kids_program
from datetime import datetime

LIBRARY_MAP = {
    "MH": ("송파위례도서관", "송파"),
    "ME": ("송파글마루도서관", "송파"),
    "MA": ("송파어린이도서관", "송파"),
    "MD": ("송파어린이영어도서관", "송파"),
    "MB": ("거마도서관", "송파"),
    "MF": ("돌마리도서관", "송파"),
    "MG": ("가락몰도서관", "송파"),
    "BC": ("소나무언덕3호도서관", "송파"),
    "BA": ("풍납도서관", "송파"),
    "BB": ("소나무언덕2호도서관", "송파"),
    "BD": ("소나무언덕4호도서관", "송파"),
    "MC": ("소나무언덕잠실본동도서관", "송파"),
    "BE": ("송이골작은도서관", "송파"),
}

BASE_URL = "https://www.splib.or.kr"
LIST_URL = f"{BASE_URL}/intro/menu/10052/program/30014/eventList.do"
MOVIE_URL = f"{BASE_URL}/intro/menu/10061/program/30016/movieList.do"

MOVIE_LIBRARIES = {
    "MA": ("송파어린이도서관", f"{BASE_URL}/spclib/menu/10290/program/30016/movieList.do"),
    "ME": ("송파글마루도서관", f"{BASE_URL}/spglib/menu/10515/program/30016/movieList.do"),
    "MH": ("송파위례도서관", None),
    "MB": ("거마도서관", None),
    "MF": ("돌마리도서관", None),
    "MG": ("가락몰도서관", None),
    "BA": ("풍납도서관", None),
    "BC": ("소나무언덕3호도서관", None),
}


async def fetch_songpa_programs() -> Tuple[List[Program], str, str]:
    """
    반환: (프로그램 목록, 상태코드 [OK / WARNING / SCHEMA_MISMATCH / ERROR], 에러 메시지)
    """
    programs: List[Program] = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    status = "OK"
    error_msg = ""
    zero_item_count = 0
    consecutive_net_errors = 0

    async with httpx.AsyncClient(verify=False, timeout=8.0) as client:
        for manage_cd, (lib_name, region) in LIBRARY_MAP.items():
            try:
                for page in [1, 2]:
                    params = {
                        "manageCd": manage_cd,
                        "currentPageNo": page,
                    }
                    try:
                        res = await client.get(LIST_URL, params=params, headers=headers)
                        consecutive_net_errors = 0
                    except Exception as net_err:
                        consecutive_net_errors += 1
                        status = "WARNING"
                        error_msg = f"송파 연결 지연: {net_err}"
                        if consecutive_net_errors >= 3 and len(programs) == 0:
                            return [], "ERROR", f"송파구 통합도서관 접속 타임아웃 (해외 IP 차단 가능성): {net_err}"
                        continue

                    if res.status_code != 200:
                        status = "WARNING"
                        error_msg = f"송파 HTTP 상태코드 {res.status_code}"
                        continue

                    soup = BeautifulSoup(res.text, "html.parser")

                    # 다중 폴백 선택자 지원
                    articles = soup.find_all(class_="article-list")
                    if not articles:
                        articles = soup.select(".event-list li, .program-list li, table.board-list tbody tr")

                    if not articles:
                        if page == 1:
                            zero_item_count += 1
                        break

                    for art in articles:
                        try:
                            title_div = art.find(class_="title") or art.find(class_="tit") or art.find("h4")
                            a_tag = (title_div.find("a") if title_div else None) or art.find("a")
                            if not a_tag:
                                continue

                            raw_title = a_tag.text.strip()
                            cleaned_title = re.sub(
                                r"^\s*(?:위례|거마|글마루|어린이|영어|돌마리|가락몰|풍납|송이골|잠실본동|[1-4]호)\s*[♠♣♥◆]*\s*",
                                "",
                                raw_title,
                            ).strip()
                            cleaned_title = " ".join(cleaned_title.split())

                            onclick = a_tag.get("onclick", "")
                            idx_match = re.search(r"fnDetail\(['\"]?(\d+)['\"]?\)", onclick)
                            event_idx = idx_match.group(1) if idx_match else None
                            if not event_idx:
                                href = a_tag.get("href", "")
                                href_match = re.search(r"eventIdx=(\d+)", href)
                                event_idx = href_match.group(1) if href_match else None

                            if not event_idx:
                                continue

                            program_id = f"songpa_{event_idx}"

                            info_blocks = art.find_all(class_="info")
                            target_raw = ""
                            fee = "무료"
                            event_period = ""
                            event_time_info = ""
                            location = ""
                            apply_period = ""

                            for block in info_blocks:
                                text = block.get_text()
                                if "대상 :" in text:
                                    target_raw = text.split("대상 :")[-1].split("수강료")[0].strip()
                                if "수강료 :" in text:
                                    fee_part = text.split("수강료 :")[-1].strip()
                                    fee = fee_part.split()[0] if fee_part else "무료"
                                if "교육기간 :" in text:
                                    dates = re.findall(r"\d{4}-\d{2}-\d{2}", text)
                                    if len(dates) >= 2:
                                        event_period = f"{dates[0]} ~ {dates[1]}"
                                    elif len(dates) == 1:
                                        event_period = dates[0]
                                    for s in block.find_all("span"):
                                        stxt = s.text.strip()
                                        if any(day in stxt for day in ["월", "화", "수", "목", "금", "토", "일"]) and ":" in stxt:
                                            event_time_info = stxt
                                        elif any(loc in stxt for loc in ["실", "관", "룸", "홀", "비대면", "온라인", "zoom", "줌"]):
                                            location = stxt
                                if "접수일정 :" in text:
                                    dates = re.findall(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}", text)
                                    if len(dates) >= 2:
                                        apply_period = f"{dates[0]} ~ {dates[1]}"
                                    elif len(dates) == 1:
                                        apply_period = dates[0]

                            status_box = art.find(class_="statusBox")
                            raw_status = ""
                            capacity = ""
                            if status_box:
                                status_el = status_box.find(class_="status")
                                if status_el:
                                    raw_status = status_el.text.strip()
                                count_el = status_box.find(class_="count")
                                if count_el:
                                    capacity = " ".join(count_el.get_text().split())

                            # 어린이/가족 프로그램 여부 엄격 검증 (성인, 시니어, 청소년 전용은 수집 제외)
                            if not is_kids_program(target_raw, cleaned_title):
                                continue

                            target_age_group, target_label = classify_target_age(target_raw, cleaned_title)
                            if target_age_group == "EXCLUDE":
                                continue

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
                            day_type, day_label = classify_day_type(event_time_info, event_start, event_end, cleaned_title)
                            is_expired = check_is_expired(event_start, event_end, apply_start, apply_end, prog_status)
                            is_new = check_is_new(apply_start, prog_status, cleaned_title, is_expired)

                            status_labels = {
                                "APPLY": "접수중",
                                "READY": "접수예정",
                                "WAIT": "대기접수",
                                "CLOSED": "마감"
                            }

                            detail_url = f"{BASE_URL}/intro/menu/10052/program/30014/eventDetail.do?eventIdx={event_idx}&manageCd={manage_cd}"

                            programs.append(Program(
                                id=program_id,
                                source="SONGPA",
                                library_name=lib_name,
                                region=region,
                                title=cleaned_title,
                                target_age_group=target_age_group,
                                target_label=target_label,
                                target_raw=target_raw,
                                day_type=day_type,
                                day_label=day_label,
                                is_new=is_new,
                                is_expired=is_expired,
                                fee=fee,
                                capacity=capacity,
                                apply_start=apply_start,
                                apply_end=apply_end,
                                event_start=event_start,
                                event_end=event_end,
                                event_time_info=event_time_info,
                                location=location or f"{lib_name} 프로그램실",
                                status=prog_status,
                                status_label=status_labels.get(prog_status, "접수중"),
                                detail_url=detail_url,
                                apply_url=detail_url
                            ))
                        except Exception as parse_err:
                            continue

            except Exception as lib_err:
                status = "WARNING"
                error_msg = f"{lib_name} 처리 실패: {lib_err}"
                continue

        # 주요 송파구 도서관 무료 어린이/가족 영화 상영(당월 + 익월)
        await _fetch_songpa_movies(client, programs, headers)

    # 13개 도서관 중 10개 이상에서 1페이지조차 0개인 경우 사이트 개편(구조 변경)으로 판정
    if zero_item_count >= 10:
        status = "SCHEMA_MISMATCH"
        error_msg = "송파구 통합도서관 페이지 구조 변경 감지(목록 태그 파싱 실패). 크롤러 점검이 필요합니다."

    return programs, status, error_msg


async def _fetch_songpa_movies(client: httpx.AsyncClient, programs: List[Program], headers: dict) -> None:
    """송파구립도서관 영화 상영 일정(당월 및 익월)을 수집합니다."""
    now = datetime.now()
    yms = [now.strftime("%Y-%m")]
    next_month_dt = datetime(now.year + (1 if now.month == 12 else 0), 1 if now.month == 12 else now.month + 1, 1)
    yms.append(next_month_dt.strftime("%Y-%m"))

    seen_movies = set()
    for manage_cd, (lib_name, direct_url) in MOVIE_LIBRARIES.items():
        for ym in yms:
            req_url = direct_url or MOVIE_URL
            params = {"searchYmd": ym} if direct_url else {"manageCd": manage_cd, "searchYmd": ym}
            try:
                res = await client.get(req_url, params=params, headers=headers)
                if res.status_code != 200:
                    continue
                soup = BeautifulSoup(res.text, "html.parser")
                for box in soup.select("div.infoBox"):
                    title_el = box.select_one("p.title")
                    if not title_el:
                        continue
                    movie_title = " ".join(title_el.get_text().split())
                    if not movie_title:
                        continue

                    info_spans = [" ".join(s.get_text().split()) for s in box.select("div.info span")]
                    rating_text = " ".join(info_spans)
                    if any(b in rating_text for b in ["15세", "18세", "청소년관람불가", "성인"]):
                        continue

                    raw_date_txt = ""
                    movie_loc = f"{lib_name} 극장"
                    for li in box.select("ul.list li"):
                        ltxt = " ".join(li.get_text().split())
                        if "상영일시" in ltxt:
                            raw_date_txt = ltxt
                        elif "상영장소" in ltxt:
                            movie_loc = ltxt.split(":", 1)[-1].strip() or movie_loc

                    dm = re.search(r"(\d{4})[.\-](\d{2})[.\-](\d{2})", raw_date_txt)
                    if not dm:
                        continue
                    event_date = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"
                    tm = re.search(r"(\d{1,2}:\d{2})", raw_date_txt)
                    time_str = tm.group(1) if tm else "16:00"
                    dow_m = re.search(r"\(([월화수목금토일])\)", raw_date_txt)
                    time_info = f"{dow_m.group(1)} {time_str}".strip() if dow_m else time_str

                    dedup_key = (manage_cd, movie_title, event_date)
                    if dedup_key in seen_movies:
                        continue
                    seen_movies.add(dedup_key)

                    is_expired = check_is_expired(event_date, event_date, None, None, "APPLY", title=movie_title)
                    if is_expired:
                        continue

                    target_raw = f"전체관람가 ({rating_text})" if rating_text else "누구나 관람"
                    if "12세" in rating_text:
                        age_group, age_label = "ELEMENTARY", "초등학생(12세)"
                    else:
                        age_group, age_label = "ALL", "누구나"

                    day_type, day_label = classify_day_type(time_info, event_date, event_date, movie_title)
                    detail_url = f"{req_url}?searchYmd={ym}" if direct_url else f"{MOVIE_URL}?manageCd={manage_cd}&searchYmd={ym}"
                    slug = re.sub(r"[^0-9A-Za-z가-힣]+", "", movie_title)[:12]
                    prog_id = f"songpa_mv_{manage_cd}_{event_date.replace('-', '')}_{slug}"

                    programs.append(
                        Program(
                            id=prog_id,
                            source="SONGPA",
                            library_name=lib_name,
                            region="송파",
                            title=f"[영화상영] {movie_title}",
                            target_age_group=age_group,
                            target_label=age_label,
                            target_raw=target_raw,
                            day_type=day_type,
                            day_label=day_label,
                            is_new=check_is_new(None, "APPLY", movie_title),
                            is_expired=False,
                            fee="무료",
                            capacity="선착순 무료 관람",
                            apply_start=None,
                            apply_end=None,
                            event_start=event_date,
                            event_end=event_date,
                            event_time_info=time_info,
                            location=movie_loc,
                            status="APPLY",
                            status_label="현장관람",
                            detail_url=detail_url,
                            apply_url=detail_url,
                        )
                    )
            except Exception:
                continue
