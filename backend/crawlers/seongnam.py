import httpx
from bs4 import BeautifulSoup
import re
from typing import List, Tuple
from models import Program
from crawlers.normalizer import classify_target_age, determine_status, classify_day_type, check_is_expired, check_is_new, is_kids_program
from datetime import datetime

BASE_URL = "https://www.snlib.go.kr"


def _extract_dates(text: str, default_year: int) -> List[str]:
    """한국어 공지 본문에서 YYYY-MM-DD 형식의 날짜 목록을 추출합니다."""
    if not text:
        return []
    cleaned = re.sub(r"[\xa0\u200b]+", " ", text)
    found: List[Tuple[int, str]] = []

    # 1. YYYY.MM.DD / YYYY-MM-DD / YYYY/MM/DD
    for m in re.finditer(r"(\d{4})\s*[.\-/]\s*(\d{1,2})\s*[.\-/]\s*(\d{1,2})", cleaned):
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            found.append((m.start(), f"{y:04d}-{mo:02d}-{d:02d}"))

    # 2. M월 D일 (연도 미표기)
    for m in re.finditer(r"(?<!\d)(\d{1,2})\s*월\s*(\d{1,2})\s*일", cleaned):
        mo, d = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            found.append((m.start(), f"{default_year:04d}-{mo:02d}-{d:02d}"))

    # 3. 연도 없이 M. D.(요일) 또는 M/D(요일) 형태 (단, 앞에 YYYY. 이 붙지 않은 경우)
    for m in re.finditer(r"(?<![.\d/])(\d{1,2})\s*[./]\s*(\d{1,2})\s*\.?(?=\s*\([월화수목금토일]\)|\s*\d{1,2}:\d{2}|\s*~|$)", cleaned):
        mo, d = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            # 이미 동일 위치에 4자리 연도 날짜로 잡혔으면 중복 방지
            if not any(abs(pos - m.start()) <= 6 for pos, _ in found):
                found.append((m.start(), f"{default_year:04d}-{mo:02d}-{d:02d}"))

    found.sort(key=lambda x: x[0])
    deduped: List[str] = []
    for _, ds in found:
        if not deduped or deduped[-1] != ds:
            deduped.append(ds)
    return deduped


async def fetch_seongnam_programs() -> Tuple[List[Program], str, str]:
    """
    반환: (프로그램 목록, 상태코드 [OK / WARNING / SCHEMA_MISMATCH / ERROR], 에러 메시지)
    """
    programs: List[Program] = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    status = "OK"
    error_msg = ""
    found_any = False

    async with httpx.AsyncClient(verify=False, timeout=12.0) as client:
        # 1. 성남위례도서관 공지사항 기반 수집
        try:
            for page in [1, 2]:
                url = f"{BASE_URL}/wr/20001/bbsPostList.do?currentPageNo={page}"
                try:
                    res = await client.get(url, headers=headers)
                except Exception as net_err:
                    status = "WARNING"
                    error_msg = f"성남 연결 오류: {net_err}"
                    continue

                if res.status_code != 200:
                    status = "WARNING"
                    error_msg = f"성남 HTTP 응답코드 {res.status_code}"
                    continue

                soup = BeautifulSoup(res.text, "html.parser")
                rows = soup.select("table tbody tr, .bbs_list li, .board-list li")

                for row in rows:
                    try:
                        tds = row.find_all("td")
                        a_tag = row.find("a")
                        if not a_tag:
                            continue

                        title_text = " ".join(a_tag.text.split())
                        # 성남위례도서관 게시판(/wr/)에 함께 뜨는 타 도서관 분관(중원어린이, 중앙, 책테마파크 등) 공지 제외
                        if re.match(r"^(중/어|중앙|책/테|분당|판교|구미|수정|무지개|수내|복정|운중|서현)(?:\s|\[|$)", title_text) and "위례" not in title_text:
                            continue
                        title_text = re.sub(r"^\s*(위례|중앙)\s*", "", title_text).strip()
                        onclick = a_tag.get("onclick", "")
                        idx_match = re.search(r"fnDetail\(['\"]?(\d+)['\"]?\)", onclick)
                        if not idx_match:
                            continue

                        post_idx = idx_match.group(1)

                        if not any(k in title_text for k in ["모집", "동화", "어린이", "독서", "체험", "특강", "교실", "강좌", "문화", "공연", "행사", "음악회", "연주회", "콘서트", "인형극", "가족", "유아", "초등", "작가"]):
                            continue
                        if any(k in title_text for k in ["휴관일", "설문조사", "공공와이파이", "시스템", "반납", "대출마감", "채용", "두배로데이", "구독", "바로대출"]):
                            continue

                        detail_url = f"{BASE_URL}/wr/20001/bbsPostDetail.do?postIdx={post_idx}"
                        found_any = True

                        det_res = await client.get(detail_url, headers=headers)
                        if det_res.status_code != 200:
                            continue

                        det_soup = BeautifulSoup(det_res.text, "html.parser")
                        content_el = det_soup.select_one(".board-view, .bbs-view, .post-content, #contentcore, .view-con")
                        content_text = content_el.get_text("\n") if content_el else ""

                        raw_target = ""
                        apply_period = ""
                        event_period = ""
                        event_time_info = ""
                        capacity = ""
                        location = "성남위례도서관"
                        apply_url = "https://sugang.seongnam.go.kr/ilms/learning/officeList.do?searchCondition1=0"

                        # 작성일에서 기본 연도 파악
                        default_year = datetime.now().year
                        ym = re.search(r"작성일\s*(\d{4})-\d{2}-\d{2}", content_text)
                        if ym:
                            default_year = int(ym.group(1))

                        clean_lines = []
                        in_header_meta = False
                        for raw_line in content_text.splitlines():
                            norm_line = re.sub(r"[\xa0\u200b]+", " ", raw_line).strip()
                            if not norm_line:
                                continue
                            if norm_line in ("이전글", "다음글"):
                                break
                            clean_lines.append(norm_line)

                        # 라벨: 값 형태 파싱 (공백 포함 라벨 대응: "►대   상:", "►일   시:")
                        body_started = False
                        body_lines = []
                        for i_l, line in enumerate(clean_lines):
                            if line in ("첨부파일", "다운로드", "바로보기"):
                                continue
                            if not body_started and line in ("목록",):
                                continue
                            body_lines.append(line)

                            if ":" in line:
                                label_part, val_part = line.split(":", 1)
                                label_key = re.sub(r"[\s►○●▶•※\-]", "", label_part)
                                val = val_part.strip()
                                if any(k in label_key for k in ["대상", "모집대상", "참여대상"]) and not raw_target:
                                    raw_target = val
                                elif any(k in label_key for k in ["장소", "운영장소", "행사장소"]) and val:
                                    location = val
                                elif any(k in label_key for k in ["인원", "모집인원", "참여인원"]) and not capacity:
                                    capacity = val
                                elif any(k in label_key for k in ["신청기간", "접수기간", "모집기간", "사전접수"]) and not apply_period:
                                    next_line = clean_lines[i_l + 1] if i_l + 1 < len(clean_lines) else ""
                                    apply_period = f"{val} {next_line}".strip() if (not val or val.endswith("~")) else val
                                elif any(k in label_key for k in ["행사일시", "운영일시", "교육일시", "일시", "일정", "운영일정", "행사일정", "운영기간", "교육기간", "행사기간"]) and not event_period:
                                    event_period = val
                            elif re.sub(r"[\s►○●▶•※\-]", "", line) in ("운영일정", "행사일정", "운영일시", "일정", "일시", "교육일정") and not event_period:
                                block_lines = []
                                for j_l in range(i_l + 1, min(i_l + 7, len(clean_lines))):
                                    nxt = clean_lines[j_l]
                                    if ":" in nxt and any(k in re.sub(r"\s+", "", nxt.split(":", 1)[0]) for k in ["신청", "접수", "장소", "대상", "문의"]):
                                        break
                                    block_lines.append(nxt)
                                event_period = " ".join(block_lines)

                        for link in det_soup.find_all("a"):
                            href = link.get("href", "")
                            if "sugang.seongnam.go.kr" in href or "learning.seongnam.go.kr" in href:
                                apply_url = href
                                break

                        if not is_kids_program(raw_target or title_text, title_text):
                            continue

                        target_age_group, target_label = classify_target_age(raw_target or title_text, title_text)
                        if target_age_group == "EXCLUDE":
                            continue

                        apply_start = None
                        apply_end = None
                        event_start = None
                        event_end = None
                        dt_start = None
                        dt_end = None

                        apply_dates = _extract_dates(apply_period, default_year)
                        if len(apply_dates) >= 1:
                            apply_start = apply_dates[0]
                            y1, m1, d1 = map(int, apply_start.split("-"))
                            dt_start = datetime(y1, m1, d1, 0, 0)
                        if len(apply_dates) >= 2:
                            apply_end = apply_dates[-1]
                            y2, m2, d2 = map(int, apply_end.split("-"))
                            dt_end = datetime(y2, m2, d2, 23, 59)

                        event_dates = _extract_dates(event_period, default_year)
                        if not event_dates:
                            # 표 기반 일정(예: '11월 4일 ... 11월 26일')이 본문에 있는 경우 시작~종료 추출
                            # 단, '신청안내' 섹션 이후 또는 표 라인에서 '신청기간' 라인 제외
                            schedule_text = "\n".join(
                                l for l in body_lines
                                if not any(k in re.sub(r"\s+", "", l) for k in ["작성일", "신청기간", "접수기간", "모집기간"])
                                and not re.match(r"^\d{4}-\d{2}-\d{2}$", l)
                            )
                            # 본문 전체에서 날짜가 2개 이상(수업 회차 표 등)인 경우만 보조 추출
                            table_dates = _extract_dates(schedule_text, default_year)
                            if len(table_dates) >= 2:
                                event_dates = [table_dates[0], table_dates[-1]]

                        if len(event_dates) >= 1:
                            event_start = event_dates[0]
                            event_end = event_dates[-1]

                        if event_period:
                            tm = re.search(r"(\d{1,2}:\d{2}\s*~\s*\d{1,2}:\d{2})", event_period)
                            if tm:
                                event_time_info = tm.group(1)

                        # 디지털 동화나라는 화~토 운영이므로 토요일(주말) 포함
                        day_info = f"화~토 {event_time_info}".strip() if "동화나라" in title_text else event_time_info
                        day_type, day_label = classify_day_type(day_info, event_start, event_end, title_text)

                        prog_status = "APPLY"
                        if "마감" in title_text or "종료" in title_text:
                            prog_status = "CLOSED"
                        elif "예정" in title_text:
                            prog_status = "READY"

                        if dt_start or dt_end:
                            prog_status = determine_status(prog_status, dt_start, dt_end)

                        is_expired = check_is_expired(event_start, event_end, apply_start, apply_end, prog_status, title=title_text)
                        is_new = check_is_new(apply_start, prog_status, title_text, is_expired)

                        status_labels = {
                            "APPLY": "접수중",
                            "READY": "접수예정",
                            "WAIT": "대기접수",
                            "CLOSED": "마감"
                        }

                        programs.append(Program(
                            id=f"seongnam_{post_idx}",
                            source="SEONGNAM",
                            library_name="성남위례도서관",
                            region="성남",
                            title=title_text,
                            target_age_group=target_age_group,
                            target_label=target_label,
                            target_raw=raw_target or "5~7세 어린이",
                            day_type=day_type,
                            day_label=day_label,
                            is_new=is_new,
                            is_expired=is_expired,
                            fee="무료",
                            capacity=capacity or "선착순 모집",
                            apply_start=apply_start,
                            apply_end=apply_end,
                            event_start=event_start,
                            event_end=event_end,
                            event_time_info=event_time_info or "상세 공지 확인",
                            location=location,
                            status=prog_status,
                            status_label=status_labels[prog_status],
                            detail_url=detail_url,
                            apply_url=apply_url
                        ))
                    except Exception:
                        continue
        except Exception as e:
            status = "WARNING"
            error_msg = f"성남 공지사항 파싱 실패: {e}"

        # 2. 캘린더 기반 수집
        try:
            cal_url = f"{BASE_URL}/wr/menu/4101478/program/30012/calendar.do"
            cal_res = await client.get(cal_url, headers=headers)
            if cal_res.status_code == 200:
                soup = BeautifulSoup(cal_res.text, "html.parser")
                cal_links = soup.find_all("a", href=lambda h: h and "bbsPostDetail.do" in h)
                seen_titles = {p.title for p in programs}

                for a in cal_links:
                    item_title = a.text.strip()
                    if not item_title or item_title in seen_titles:
                        continue
                    if any(k in item_title for k in ["휴관", "공사", "선거"]):
                        continue

                    if not is_kids_program(item_title, item_title):
                        continue

                    seen_titles.add(item_title)
                    target_age_group, target_label = classify_target_age(item_title, item_title)
                    if target_age_group == "EXCLUDE":
                        continue
                    cal_day_type, cal_day_label = classify_day_type("화~토" if "동화나라" in item_title else "", None, None, item_title)
                    href = a.get("href", "")

                    post_id = "cal_" + re.sub(r"\W+", "_", item_title)
                    idx_match = re.search(r"postIdx=(\d+)", href)
                    if idx_match:
                        post_id = f"seongnam_cal_{idx_match.group(1)}"

                    found_any = True
                    programs.append(Program(
                        id=post_id,
                        source="SEONGNAM",
                        library_name="성남위례도서관",
                        region="성남",
                        title=f"[정규/체험] {item_title}",
                        target_age_group=target_age_group,
                        target_label=target_label,
                        target_raw="위례도서관 정규 프로그램",
                        day_type=cal_day_type,
                        day_label=cal_day_label,
                        is_new=False,
                        is_expired=False,
                        fee="무료",
                        capacity="정원제",
                        apply_start=None,
                        apply_end=None,
                        event_start=None,
                        event_end=None,
                        event_time_info="매월 정기 운영",
                        location="성남위례도서관 4층/배움터",
                        status="APPLY",
                        status_label="접수중",
                        detail_url=href if href.startswith("http") else f"{BASE_URL}{href}",
                        apply_url="https://sugang.seongnam.go.kr/ilms/learning/officeList.do?searchCondition1=0"
                    ))
        except Exception as e:
            pass

        if not found_any and status == "OK":
            status = "SCHEMA_MISMATCH"
            error_msg = "성남위례도서관 게시판/캘린더 파싱 실패"

    return programs, status, error_msg
