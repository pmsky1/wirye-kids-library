"""
체험관, 문화공간 및 송파구 공식 소식지(송파소식) 유아/초등/누구나 행사 크롤러
- 송파어린이문화회관 상설 체험관 + 실시간 재능/문화 강좌(songpakids.com)
- 송파소식 웹진(songpa.newstool.co.kr) 최신호 특집/청소년/문화캘린더 유아·어린이·가족·누구나 행사
"""
from datetime import datetime, timedelta
import hashlib
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
)

SONGPAKIDS_BASE = "https://www.songpakids.com"
SONGPAKIDS_TALENT_URL = f"{SONGPAKIDS_BASE}/site/main/edu/TALENT/list"

NEWSTOOL_BASE = "https://songpa.newstool.co.kr"
NEWSTOOL_LIST_URL = f"{NEWSTOOL_BASE}/list.php"


def _make_id(prefix: str, key: str) -> str:
    return f"{prefix}_{hashlib.md5(key.encode('utf-8')).hexdigest()[:10]}"


def _parse_korean_date_token(token: str, default_year: int, prev_month: Optional[int] = None) -> Optional[str]:
    """'2026.12.30', '2027. 1.31', '12. 5' 등을 'YYYY-MM-DD'로 변환합니다."""
    m = re.search(r"(?:(\d{4})\s*[.\-년]\s*)?(\d{1,2})\s*[.\-월]\s*(\d{1,2})", token or "")
    if not m:
        return None
    y = int(m.group(1)) if m.group(1) else default_year
    mo = int(m.group(2))
    d = int(m.group(3))
    if not m.group(1) and prev_month and mo < prev_month:
        y += 1
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return None
    return f"{y:04d}-{mo:02d}-{d:02d}"


def _extract_date_range(text: str, default_year: int) -> Tuple[Optional[str], Optional[str]]:
    if not text:
        return None, None
    matches = list(re.finditer(r"(?:(\d{4})\s*[.\-년]\s*)?(\d{1,2})\s*[.\-월]\s*(\d{1,2})", text))
    if not matches:
        return None, None
    start = _parse_korean_date_token(matches[0].group(0), default_year)
    if not start:
        return None, None
    start_year = int(start[:4])
    start_month = int(start[5:7])
    if len(matches) >= 2:
        end = _parse_korean_date_token(matches[-1].group(0), start_year, prev_month=start_month) or start
    else:
        end = start
    return start, end


def _is_adult_or_excluded_event(title: str, target: str, body: str) -> bool:
    """성인 전용 강좌, 수험생 콘서트, 유료 기기 대여(에듀ON), 기관 대상 사업, 중복 강좌를 제외합니다."""
    combined = f"{title} {target} {body}"
    exclude_terms = [
        "수험생",
        "에듀ON",
        "패드",
        "대여형",
        "여성문화회관",
        "여성경력이음",
        "시니어",
        "어르신",
        "당구교실",
        "성인취미",
        "생활문화대학",
        "통장 모집",
        "지역아동센터",
        "정보화교육",
        "원어민 영어캠프",  # songpa_learn.py에서 위례/헤드/풍납 세부 반별로 직접 수집
        "송파진로체험지원센터",  # songpa_learn.py에서 직접 수집
        "평생학습원",  # songpa_learn.py에서 직접 수집
        "어린이새싹극장",  # songpa.py movieList.do에서 직접 수집
        "주민동아리 상시모집",
        "송파구의회",
    ]
    return any(term in combined for term in exclude_terms)


async def _fetch_songpakids_talent(client: httpx.AsyncClient) -> List[Program]:
    """송파어린이문화회관 실시간 재능/문화 강좌를 수집합니다."""
    items: List[Program] = []
    try:
        resp = await client.get(SONGPAKIDS_TALENT_URL, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"[Experience Crawler] SongpaKids talent fetch warning: {e}")
        return items

    soup = BeautifulSoup(resp.text, "html.parser")
    seen_ids = set()

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        m = re.search(r"/site/main/edu/(\d+)$", href)
        if not m:
            continue
        edu_id = m.group(1)
        if edu_id in seen_ids:
            continue
        seen_ids.add(edu_id)

        title_el = a.select_one("p.title")
        if not title_el:
            continue
        title = " ".join(title_el.get_text(" ", strip=True).split())
        if not title:
            continue

        status_el = a.select_one("span.current")
        raw_status = status_el.get_text(" ", strip=True) if status_el else ""

        fields: Dict[str, str] = {}
        for dl in a.find_all("dl"):
            dts = dl.find_all("dt")
            dds = dl.find_all("dd")
            for dt, dd in zip(dts, dds):
                k = re.sub(r"\s+", "", dt.get_text(" ", strip=True))
                v = " ".join(dd.get_text(" ", strip=True).split())
                if k:
                    fields[k] = v

        target_raw = fields.get("강의대상", "유아 및 어린이")
        event_period = fields.get("강의기간", "")
        event_time = fields.get("강의시간", "")
        capacity = fields.get("강의정원", "")
        fee = fields.get("수강료", "홈페이지 참조")

        event_start, event_end = _extract_date_range(event_period, datetime.now().year)

        age_group, age_label = classify_target_age(target_raw, title)
        day_type, day_label = classify_day_type(event_time, event_start, event_end, title)

        status_code = determine_status(raw_status, None, None)
        status_label_map = {
            "APPLY": "접수중",
            "READY": "접수예정",
            "WAIT": "대기접수",
            "CLOSED": raw_status or "모집마감",
        }
        status_label = status_label_map.get(status_code, raw_status or "접수중")

        if check_is_expired(event_start, event_end, None, None, status_code, title):
            continue

        detail_url = f"{SONGPAKIDS_BASE}{href}" if href.startswith("/") else href

        items.append(
            Program(
                id=f"exp_songpakids_{edu_id}",
                source="EXPERIENCE",
                library_name="송파어린이문화회관",
                region="송파",
                title=title,
                target_age_group=age_group,
                target_label=age_label,
                target_raw=target_raw,
                day_type=day_type,
                day_label=day_label,
                is_new=check_is_new(None, status_code, title),
                is_expired=False,
                fee=fee,
                capacity=capacity,
                event_start=event_start,
                event_end=event_end,
                event_time_info=event_time or None,
                location="서울 송파구 중대로 235 (오금역 1번 출구)",
                status=status_code,
                status_label=status_label,
                detail_url=detail_url,
                apply_url=detail_url,
            )
        )

    return items


def _clean_article_lines(soup: BeautifulSoup) -> Tuple[str, List[str], List[Tuple[str, str]]]:
    """송파소식 웹진 기사에서 본문 텍스트 줄과 외부 링크를 추출합니다."""
    title_text = ""
    h_title = soup.find("title")
    if h_title:
        title_text = h_title.get_text(" ", strip=True).replace(" - 송파소식.", "").strip()

    ext_links: List[Tuple[str, str]] = []
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if href.startswith("http") and not any(
            skip in href
            for skip in (
                "newstool.co.kr",
                "twitter.com",
                "facebook.com",
                "band.us",
                "songpa.go.kr/ebookreal",
                "recptApplStep1.do",
            )
        ):
            ext_links.append((href, a.get_text(" ", strip=True)))

    raw_lines = [l.strip() for l in soup.get_text("\n", strip=True).splitlines() if l.strip()]
    # 본문 시작 마커("기본") 이후 ~ 푸터("PDF보기" / "송파소식 20") 이전까지만 추출
    start_idx = 0
    end_idx = len(raw_lines)
    for i, line in enumerate(raw_lines):
        if line == "기본":
            start_idx = i + 1
            break
    for i in range(start_idx, len(raw_lines)):
        if raw_lines[i] in ("PDF보기", "ebook보기", "SNS공유") or raw_lines[i].startswith("등록일 :"):
            end_idx = i
            break

    return title_text, raw_lines[start_idx:end_idx], ext_links


def _extract_kv_from_lines(lines: List[str]) -> Dict[str, str]:
    """['일시', '12. 5.(토) ...', '대상', '초등학생'] 형태의 줄 목록을 dict로 묶습니다."""
    keys = {
        "일시",
        "기간",
        "운영시간",
        "대상",
        "응모 자격",
        "응모 기간",
        "응모 방법",
        "장소",
        "위치",
        "이용요금",
        "관람료",
        "입장료",
        "수강료",
        "내용",
        "신청",
        "예매",
        "예매일",
        "접수방법",
        "문의",
        "상영시간",
        "주요시설",
        "주최·주관",
        "주최",
        "주관",
        "협력",
        "주요작가",
    }
    kv: Dict[str, str] = {}
    cur_key: Optional[str] = None
    for line in lines:
        if line in keys:
            cur_key = line
            kv.setdefault(cur_key, "")
        elif cur_key:
            kv[cur_key] = f"{kv[cur_key]} {line}".strip()
    return kv


def _parse_newstool_article(
    aid: str,
    detail_url: str,
    article_title: str,
    lines: List[str],
    ext_links: List[Tuple[str, str]],
    issue_year: int,
) -> List[Program]:
    """송파소식 기사 본문에서 유아/초등/누구나 문화·체험·특집 행사를 파싱합니다."""
    if not lines:
        return []

    programs: List[Program] = []
    full_text = "\n".join(lines)
    now_str = datetime.now().strftime("%Y-%m-%d")

    def make_prog(
        sub_key: str,
        library_name: str,
        title: str,
        target_raw: str,
        event_start: Optional[str],
        event_end: Optional[str],
        event_time_info: Optional[str],
        location: str,
        fee: str = "무료",
        capacity: str = "상세 페이지 참조",
        apply_start: Optional[str] = None,
        apply_end: Optional[str] = None,
        apply_url: Optional[str] = None,
        day_type_override: Optional[str] = None,
        day_label_override: Optional[str] = None,
        target_group_override: Optional[str] = None,
        target_label_override: Optional[str] = None,
        status_code: str = "APPLY",
        status_label: str = "안내중",
    ) -> Optional[Program]:
        if _is_adult_or_excluded_event(title, target_raw, f"{location} {event_time_info or ''}"):
            return None
        if check_is_expired(event_start, event_end, apply_start, apply_end, status_code, title):
            return None

        if target_group_override and target_label_override:
            age_group, age_label = target_group_override, target_label_override
        else:
            age_group, age_label = classify_target_age(target_raw, title)

        if day_type_override and day_label_override:
            day_type, day_label = day_type_override, day_label_override
        else:
            day_type, day_label = classify_day_type(event_time_info or "", event_start, event_end, title)

        return Program(
            id=_make_id("news", f"{aid}_{sub_key}"),
            source="EXPERIENCE",
            library_name=library_name,
            region="송파",
            title=title,
            target_age_group=age_group,
            target_label=age_label,
            target_raw=target_raw,
            day_type=day_type,
            day_label=day_label,
            is_new=check_is_new(apply_start, status_code, title),
            is_expired=False,
            fee=fee,
            capacity=capacity,
            apply_start=apply_start,
            apply_end=apply_end,
            event_start=event_start,
            event_end=event_end,
            event_time_info=event_time_info,
            location=location,
            status=status_code,
            status_label=status_label,
            detail_url=detail_url,
            apply_url=apply_url or detail_url,
        )

    # 1) [겨울방학 특집] 기사: 하하호호 눈썰매장 + 청소년/어린이/가족 특강·축제
    if "하하호호 눈썰매장" in full_text or "겨울방학 특집" in article_title:
        # 1-1. 하하호호 눈썰매장
        if "하하호호 눈썰매장" in full_text:
            sled_idx = next((i for i, l in enumerate(lines) if "하하호호 눈썰매장" in l), 0)
            sled_slice = lines[sled_idx : min(len(lines), sled_idx + 28)]
            kv = _extract_kv_from_lines(sled_slice)
            sled_period = " ".join(sled_slice[:5])
            e_start, e_end = _extract_date_range(sled_period, issue_year)
            p = make_prog(
                sub_key="sled",
                library_name="가든파이브(송파구)",
                title="[겨울특집] 송파구 하하호호 눈썰매장 (대형/소형 슬로프, 얼음썰매, 체험)",
                target_raw=kv.get("대상", "3세~12세 미만 아동"),
                event_start=e_start,
                event_end=e_end,
                event_time_info=f"{e_start or ''}~{e_end or ''} 10:00~17:00 (1, 2, 3부 운영)",
                location="가든파이브 라이프 중앙광장",
                fee=kv.get("이용요금", "무료"),
                capacity="동시 이용 400명 이내",
                day_type_override="WEEKEND",
                day_label_override="주말/매일",
                target_group_override="ALL",
                target_label_override="유아 및 초등 (3~12세)",
                status_label="운영안내",
            )
            if p:
                programs.append(p)

        # 1-2. 하하호호 페스티벌 / 스키체험 캠프 / 오금 DAY / 해피오케스트라
        known_headings = [
            "2026 하하호호 페스티벌",
            "청소년 겨울 스키체험 캠프",
            "크리스마스 기념 오금 DAY",
            "제12회 해피오케스트라 정기연주회",
        ]
        for h_idx, heading in enumerate(known_headings):
            pos = next((i for i, l in enumerate(lines) if heading in l), None)
            if pos is None:
                continue
            next_pos = len(lines)
            for other in known_headings[h_idx + 1 :] + ["겨울방학 원어민 영어캠프"]:
                o_pos = next((i for i in range(pos + 1, len(lines)) if other in lines[i]), None)
                if o_pos is not None:
                    next_pos = min(next_pos, o_pos)
            block = lines[pos + 1 : next_pos]
            kv = _extract_kv_from_lines(block)
            when_txt = kv.get("일시") or kv.get("기간") or ""
            e_start, e_end = _extract_date_range(when_txt, issue_year)
            raw_target = kv.get("대상", "어린이 및 가족")
            loc = kv.get("장소", "송파구 청소년센터")

            if "하하호호 페스티벌" in heading:
                p = make_prog(
                    sub_key="haha_festival",
                    library_name="잠실청소년센터",
                    title="[겨울특집] 2026 하하호호 페스티벌 (체험부스, 먹거리, 공연마당)",
                    target_raw="어린이 및 지역주민 누구나",
                    event_start=e_start,
                    event_end=e_end,
                    event_time_info=when_txt,
                    location=loc,
                    fee="무료",
                    capacity="현장 참여 가능",
                    day_type_override="WEEKEND",
                    day_label_override="주말(토)",
                    target_group_override="ALL",
                    target_label_override="누구나",
                    status_label="현장참여",
                )
                if p:
                    programs.append(p)
            elif "스키체험 캠프" in heading:
                p = make_prog(
                    sub_key="ski_camp",
                    library_name="송파청소년센터",
                    title="[겨울특집] 송파청소년센터 겨울 스키체험 캠프 (2박3일)",
                    target_raw="초등 4~6학년 (및 중1~3)",
                    event_start=e_start,
                    event_end=e_end,
                    event_time_info=when_txt,
                    location=loc,
                    fee="150,000원",
                    capacity="선착순 80명",
                    apply_url="https://www.songpayouth.or.kr/",
                    day_type_override="WEEKEND",
                    day_label_override="주말포함(금~일)",
                    target_group_override="ELEMENTARY",
                    target_label_override="초등학생",
                    status_label="접수안내",
                )
                if p:
                    programs.append(p)
            elif "오금 DAY" in heading:
                p = make_prog(
                    sub_key="ogeum_day",
                    library_name="오금청소년센터",
                    title="[겨울특집] 크리스마스 기념 오금 DAY (트리 오너먼트, 쿠키 만들기)",
                    target_raw="9세 이상 초등학생 및 가족 누구나",
                    event_start=e_start,
                    event_end=e_end,
                    event_time_info=when_txt,
                    location=loc,
                    fee="무료/재료비 안내",
                    capacity="선착순 모집",
                    apply_url="https://www.ogeum.or.kr/",
                    day_type_override="WEEKDAY",
                    day_label_override="평일(금)",
                    target_group_override="ELEMENTARY",
                    target_label_override="초등/가족 (9세~)",
                    status_label="접수안내",
                )
                if p:
                    programs.append(p)
            elif "해피오케스트라" in heading:
                p = make_prog(
                    sub_key="happy_orchestra",
                    library_name="마천청소년센터",
                    title="[송파소식] 제12회 해피오케스트라 정기연주회",
                    target_raw="송파구민 누구나",
                    event_start=e_start,
                    event_end=e_end,
                    event_time_info=when_txt,
                    location=loc,
                    fee="무료",
                    capacity="현장 선착순",
                    day_type_override="WEEKDAY",
                    day_label_override="평일(목)",
                    target_group_override="ALL",
                    target_label_override="누구나",
                    status_label="무료공연",
                )
                if p:
                    programs.append(p)

    # 2) [청소년 정보] 기사: 베이킹 특강 / 오금 스튜디오 / 겨울방학특강
    if "청소년 정보" in article_title or "리스 도넛 만들기" in full_text:
        forms_url = next((u for u, _ in ext_links if "forms.gle" in u), None)
        naver_url = next((u for u, _ in ext_links if "naver.me" in u), None)

        sub_headings = [
            "베이킹 특강 [리스 도넛 만들기]",
            "오금 스튜디오",
            "송파청소년센터 겨울방학특강 회원 모집",
            "〈디지털 밸런스 UP〉",
        ]
        for idx, heading in enumerate(sub_headings[:3]):
            pos = next((i for i, l in enumerate(lines) if heading in l), None)
            if pos is None:
                continue
            next_pos = len(lines)
            for other in sub_headings[idx + 1 :]:
                o_pos = next((i for i in range(pos + 1, len(lines)) if other in lines[i]), None)
                if o_pos is not None:
                    next_pos = min(next_pos, o_pos)
            block = lines[pos + 1 : next_pos]
            kv = _extract_kv_from_lines(block)
            when_txt = kv.get("일시", "")
            e_start, e_end = _extract_date_range(when_txt, issue_year)

            if "리스 도넛 만들기" in heading:
                p = make_prog(
                    sub_key="baking_donut",
                    library_name="마천청소년센터",
                    title="베이킹 특강 [리스 도넛 만들기]",
                    target_raw=kv.get("대상", "유아 7세 ~ 초등 6학년"),
                    event_start=e_start,
                    event_end=e_end,
                    event_time_info=when_txt,
                    location=kv.get("장소", "마천청소년센터 3층 도담도담실"),
                    fee="센터 문의",
                    capacity="15명 선착순",
                    apply_url=forms_url or detail_url,
                    day_type_override="WEEKEND",
                    day_label_override="주말(토)",
                    target_group_override="ALL",
                    target_label_override="유아 및 초등 (7세~초6)",
                    status_label="접수중",
                )
                if p:
                    programs.append(p)
            elif "오금 스튜디오" in heading:
                p = make_prog(
                    sub_key="ogeum_studio",
                    library_name="오금청소년센터",
                    title="다문화 가족 사진 촬영 [오금 스튜디오] (액자 제공)",
                    target_raw=kv.get("대상", "다문화 가족"),
                    event_start=e_start,
                    event_end=e_end,
                    event_time_info=when_txt,
                    location=kv.get("장소", "오금청소년센터 1층 공간"),
                    fee="무료",
                    capacity="선착순 모집",
                    apply_url=naver_url or detail_url,
                    day_type_override="WEEKEND",
                    day_label_override="주말(토)",
                    target_group_override="FAMILY",
                    target_label_override="가족/누구나",
                    status_label="접수중",
                )
                if p:
                    programs.append(p)
            elif "겨울방학특강" in heading:
                a_start, _ = _extract_date_range(kv.get("신청", ""), issue_year)
                p = make_prog(
                    sub_key="songpa_winter_special",
                    library_name="송파청소년센터",
                    title="송파청소년센터 겨울방학특강 (코딩, 미술, 베이킹)",
                    target_raw=kv.get("대상", "초등학생"),
                    event_start=e_start,
                    event_end=e_end,
                    event_time_info=when_txt,
                    location=kv.get("장소", "송파청소년센터 강의실"),
                    fee="홈페이지 참조",
                    capacity="선착순 모집",
                    apply_start=a_start,
                    apply_url="https://www.songpayouth.or.kr/",
                    day_type_override="WEEKDAY",
                    day_label_override="평일(월~금)",
                    target_group_override="ELEMENTARY",
                    target_label_override="초등학생",
                    status_code="READY" if a_start and a_start > now_str else "APPLY",
                    status_label="접수예정" if a_start and a_start > now_str else "접수중",
                )
                if p:
                    programs.append(p)

    # 3) [문화캘린더] 기사: 글마루 숲속극장 12월 무료 영화 4편 + 석촌호수 아뜰리에 콘서트
    if "문화캘린더" in article_title or "글마루 숲속극장" in full_text:
        yeyak_url = next((u for u, _ in ext_links if "yeyak.seoul.go.kr" in u), "https://yeyak.seoul.go.kr")

        # 3-1. 석촌호수 아뜰리에 연말 콘서트
        if "석촌호수 아뜰리에 연말 콘서트" in full_text:
            pos = next(i for i, l in enumerate(lines) if "석촌호수 아뜰리에 연말 콘서트" in l)
            end_pos = next((i for i in range(pos + 1, len(lines)) if "송파여성문화회관" in lines[i]), min(len(lines), pos + 30))
            block = lines[pos + 1 : end_pos]
            kv = _extract_kv_from_lines(block)
            e_start, e_end = _extract_date_range(kv.get("일시", ""), issue_year)
            p = make_prog(
                sub_key="impact_on_concert",
                library_name="석촌호수 아뜰리에",
                title="[문화캘린더] 석촌호수 아뜰리에 연말 콘서트 <2026임팩트온>",
                target_raw="누구나 (가족 관람 가능)",
                event_start=e_start,
                event_end=e_end,
                event_time_info=kv.get("일시", "19:00 (주말 총 5회)"),
                location="석촌호수 아뜰리에 (110석)",
                fee="서울시 공공예약 참조",
                capacity="110석",
                apply_url=yeyak_url,
                day_type_override="WEEKEND",
                day_label_override="주말(토, 일)",
                target_group_override="ALL",
                target_label_override="누구나",
                status_label="예약접수",
            )
            if p:
                programs.append(p)

        # 3-2. 글마루 숲속극장 영화 상영 일정 (songpa.py movieList.do에서 미등록 시 자동 보완)
        if "글마루 숲속극장" in full_text:
            mv_idx = next((i for i, l in enumerate(lines) if l == "글마루 숲속극장"), None)
            if mv_idx is not None:
                stop_idx = next(
                    (i for i in range(mv_idx + 1, len(lines)) if "어린이새싹극장" in lines[i] or "사정에 따라" in lines[i]),
                    min(len(lines), mv_idx + 25),
                )
                mv_lines = lines[mv_idx + 1 : stop_idx]
                time_txt = next((mv_lines[i + 1] for i, l in enumerate(mv_lines[:-1]) if l == "상영시간"), "16시")
                for i, line in enumerate(mv_lines):
                    dm = re.match(r"^(\d{1,2})\s*\.\s*(\d{1,2})\s*\.\s*\((일|토|금|월|화|수|목)\)$", line)
                    if dm and i + 1 < len(mv_lines):
                        movie_title = mv_lines[i + 1]
                        if len(movie_title) < 2 or movie_title.startswith("※"):
                            continue
                        mo, day, dow = int(dm.group(1)), int(dm.group(2)), dm.group(3)
                        screen_date = f"{issue_year:04d}-{mo:02d}-{day:02d}"
                        p = make_prog(
                            sub_key=f"glmaru_movie_{screen_date}",
                            library_name="송파글마루도서관",
                            title=f"[무료영화] {movie_title}",
                            target_raw="전체관람/누구나 (어린이 및 가족)",
                            event_start=screen_date,
                            event_end=screen_date,
                            event_time_info=f"{screen_date} ({dow}) {time_txt}",
                            location="송파글마루도서관 지하 1층 숲속극장",
                            fee="무료",
                            capacity="현장 선착순 입장",
                            apply_url="https://www.splib.or.kr/spjlib/index.do",
                            day_type_override="WEEKEND" if dow in ("토", "일") else "WEEKDAY",
                            day_label_override=f"주말({dow})" if dow in ("토", "일") else f"평일({dow})",
                            target_group_override="ALL",
                            target_label_override="누구나",
                            status_label="무료상영",
                        )
                        if p:
                            programs.append(p)

    # 4) [문화예술의 도시 송파] 기사: 더 갤러리 호수 거장전 + 송파구립 민속예술단 정기연주회
    if "문화예술의 도시 송파" in article_title or "한국근현대미술거장전" in full_text:
        if "한국근현대미술거장전" in full_text:
            pos = next(i for i, l in enumerate(lines) if "한국근현대미술거장전" in l)
            end_pos = next((i for i in range(pos + 1, len(lines)) if "힐링콘서트" in lines[i] or "크리스마스 트리" in lines[i]), min(len(lines), pos + 35))
            block = lines[pos : end_pos]
            kv = _extract_kv_from_lines(block)
            e_start, e_end = _extract_date_range(" ".join(block[:6]), issue_year)
            p = make_prog(
                sub_key="masterpieces_100years",
                library_name="더 갤러리 호수",
                title="[무료전시] 한국근현대미술거장전: 100년의 울림 (이중섭, 박수근, 김환기 등)",
                target_raw="송파구민 및 방문객 누구나 (어린이 및 가족 관람 추천)",
                event_start=e_start,
                event_end=e_end,
                event_time_info=kv.get("운영시간", "10:00~19:00 (월 휴관, 토 21:00)"),
                location="더 갤러리 호수 (석촌호수)",
                fee=kv.get("관람료", "무료"),
                capacity="상설 무료 관람",
                day_type_override="WEEKEND",
                day_label_override="주말포함(화~일)",
                target_group_override="ALL",
                target_label_override="누구나",
                status_label="무료관람",
            )
            if p:
                programs.append(p)

        if "민속예술단 정기연주회" in full_text:
            pos = next(i for i, l in enumerate(lines) if "민속예술단 정기연주회" in l)
            block = lines[pos : min(len(lines), pos + 20)]
            kv = _extract_kv_from_lines(block)
            e_start, e_end = _extract_date_range(kv.get("일시", ""), issue_year)
            a_start, _ = _extract_date_range(kv.get("예매일", ""), issue_year)
            p = make_prog(
                sub_key="folk_orchestra",
                library_name="송파문화예술회관",
                title="[무료공연] 제30회 송파구립 민속예술단 정기연주회: 항해 “빛으로의 여행”",
                target_raw="송파구민 누구나",
                event_start=e_start,
                event_end=e_end,
                event_time_info=kv.get("일시", "15:30"),
                location=kv.get("장소", "송파문화예술회관 3층 아트홀"),
                fee="무료 (네이버 선착순 예매)",
                capacity="선착순 예매",
                apply_start=a_start,
                day_type_override="WEEKEND",
                day_label_override="주말(토)",
                target_group_override="ALL",
                target_label_override="누구나",
                status_code="READY" if a_start and a_start > now_str else "APPLY",
                status_label="예매예정" if a_start and a_start > now_str else "예매중",
            )
            if p:
                programs.append(p)

    # 5) [그림이벤트] 독자참여: 유아/초등/구민 누구나 응모 가능
    if "그림이벤트" in article_title or "그림 그리기" in full_text:
        kv = _extract_kv_from_lines(lines)
        _, a_end = _extract_date_range(kv.get("응모 기간", ""), issue_year)
        p = make_prog(
            sub_key="drawing_event",
            library_name="송파소식(송파구청)",
            title="[참여이벤트] 하하호호와 신나는 겨울을 즐겨요! 그림 색칠 이벤트",
            target_raw="송파구민 누구나 (유아, 초등, 가족)",
            event_start=now_str,
            event_end=a_end,
            event_time_info=kv.get("응모 기간", "매달 진행"),
            location="이메일 접수 (songpasosik@naver.com)",
            fee="무료 (선정 시 모바일 쿠폰)",
            capacity="응모자 선정",
            apply_end=a_end,
            day_type_override="WEEKEND",
            day_label_override="상시/이메일",
            target_group_override="ALL",
            target_label_override="누구나",
            status_label="응모중",
        )
        if p:
            programs.append(p)

    return programs


async def _fetch_songpa_newstool(client: httpx.AsyncClient) -> List[Program]:
    """송파소식 웹진(songpa.newstool.co.kr) 최신호에서 유아·초등·누구나 행사를 수집합니다."""
    items: List[Program] = []
    try:
        list_resp = await client.get(NEWSTOOL_LIST_URL, timeout=15)
        list_resp.raise_for_status()
    except Exception as e:
        print(f"[Experience Crawler] Songpa Newstool list fetch warning: {e}")
        return items

    soup = BeautifulSoup(list_resp.text, "html.parser")
    page_text = soup.get_text(" ", strip=True)
    y_match = re.search(r"(20\d{2})\s*년\s*(\d{1,2})\s*월호", page_text)
    issue_year = int(y_match.group(1)) if y_match else datetime.now().year

    target_links: List[Tuple[str, str, str]] = []
    seen_aids = set()
    relevant_keywords = ("겨울방학 특집", "청소년 정보", "문화캘린더", "문화예술의 도시", "그림이벤트")

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        text = " ".join(a.get_text(" ", strip=True).split())
        m = re.search(r"aid=(\d+)", href)
        if not m:
            continue
        aid = m.group(1)
        if aid in seen_aids:
            continue
        if any(k in text for k in relevant_keywords):
            seen_aids.add(aid)
            abs_url = f"{NEWSTOOL_BASE}/{href.lstrip('./')}"
            target_links.append((aid, abs_url, text))

    for aid, url, link_title in target_links:
        try:
            vr = await client.get(url, timeout=15)
            vr.raise_for_status()
            vs = BeautifulSoup(vr.text, "html.parser")
            article_title, lines, ext_links = _clean_article_lines(vs)
            parsed = _parse_newstool_article(
                aid=aid,
                detail_url=url,
                article_title=article_title or link_title,
                lines=lines,
                ext_links=ext_links,
                issue_year=issue_year,
            )
            items.extend(parsed)
        except Exception as e:
            print(f"[Experience Crawler] Songpa Newstool aid={aid} warning: {e}")

    return items


async def fetch_experience_programs() -> Tuple[List[Program], str, Optional[str]]:
    programs: List[Program] = []
    status = "OK"
    error_msg = None
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d")

    hub_experiences = [
        {
            "id": "exp_spscc_child_culture",
            "library_name": "송파어린이문화회관",
            "region": "송파",
            "title": "[상상놀이터] 송파어린이문화회관 키움체험(과학/직업/오감) 및 주말 체험극",
            "target_age_group": "PRESCHOOL",
            "target_label": "유치원/유아 (4~7세)",
            "target_raw": "영유아 (4~7세) 및 보호자",
            "day_type": "WEEKEND",
            "day_label": "주말(토)",
            "fee": "3,000원",
            "capacity": "회차당 30명 정원제",
            "event_time_info": "1부 10:00 / 2부 13:00 / 3부 15:30",
            "location": "서울 송파구 중대로 235 (오금역 1번 출구)",
            "status": "APPLY",
            "status_label": "접수중",
            "detail_url": "https://www.songpakids.com/site/main/content/playexperience01",
            "apply_url": "https://www.songpakids.com/site/main/edu/IMAGINE/list?floorType=SECOND",
        }
    ]

    for item in hub_experiences:
        programs.append(
            Program(
                id=item["id"],
                source="EXPERIENCE",
                library_name=item["library_name"],
                region=item["region"],
                title=item["title"],
                target_age_group=item["target_age_group"],
                target_label=item["target_label"],
                target_raw=item["target_raw"],
                day_type=item["day_type"],
                day_label=item["day_label"],
                is_new=False,
                is_expired=False,
                fee=item["fee"],
                capacity=item["capacity"],
                apply_start=None,
                apply_end=None,
                event_start=f"{now.year}-{now.month:02d}-01",
                event_end=f"{now.year}-{now.month:02d}-28",
                event_time_info=item["event_time_info"],
                location=item["location"],
                status=item["status"],
                status_label=item["status_label"],
                detail_url=item["detail_url"],
                apply_url=item["apply_url"],
            )
        )

    async with httpx.AsyncClient(verify=False, follow_redirects=True) as client:
        talent_items = await _fetch_songpakids_talent(client)
        newstool_items = await _fetch_songpa_newstool(client)

    programs.extend(talent_items)
    programs.extend(newstool_items)

    # ID 기준 중복 제거
    deduped: Dict[str, Program] = {}
    for p in programs:
        deduped[p.id] = p

    return list(deduped.values()), status, error_msg
