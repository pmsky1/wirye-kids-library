"""
연령 및 프로그램 상태, 주말/평일 정규화 모듈
"""
import re
from datetime import datetime, timedelta, timezone
from typing import Tuple, Optional

KST = timezone(timedelta(hours=9))


def is_kids_program(raw_target: str, title: str = "") -> bool:
    """
    어린이(유아 4~7세, 영아 0~3세, 초등 1~6학년, 가족 동반, 전연령 누구나) 체험/문화 프로그램인지 검증합니다.
    성인 전용, 시니어/어르신 전용, 청소년 이상 전용 프로그램 및 성인 독서모임 등은 False를 반환하여 제외합니다.
    """
    target = (raw_target or "").strip().lower()
    t = (title or "").strip().lower()
    combined = f"{target} {t}"

    # 1. 학부모/부모/양육자 단독 대상 강의(성인 교육) 배제 후, 아이와 함께 참여하는 가족 동반 여부 확인
    is_parent_only = bool(re.search(r'(부모표|학부모\s*(?:특강|교육|교실|아카데미)|부모\s*(?:특강|교육|아카데미)|양육자\s*(?:특강|교육)|자녀를\s*둔)', combined))
    is_family_event = (not is_parent_only) and bool(
        re.search(
            r'(아이와|자녀와|자녀\s*동반|유아\s*동반|아동\s*동반|어린이\s*\+\s*(?:보호자|부모|양육자)|가족\s*동반|가족과\s*함께|가족|온가족|보호자\s*동반|부모\s*동반)',
            combined,
        )
    )

    # 2. 명백한 비어린이(성인/시니어/청소년 이상) 배제 키워드
    exclude_keywords = [
        r'시니어', r'어르신', r'노인', r'6[0-9]세\s*이상', r'실버',
        r'청소년\s*이상', r'중고등', r'중학생', r'고등학생', r'1[4-9]세\s*이상',
        r'성인', r'학부모', r'양육자', r'교사', r'일반\s*인', r'1인가구',
    ]

    for pat in exclude_keywords:
        if re.search(pat, target) or re.search(pat, t):
            if is_parent_only or ('학부모' in target and not is_family_event):
                return False
            if not is_family_event:
                return False

    # 3. 긍정적 어린이 키워드 확인
    kids_keywords = [
        r'유아', r'유치', r'미취학', r'[0-7]세', r'개월', r'베이비', r'북스타트',
        r'어린이', r'아동', r'초등', r'초\s*[1-6]', r'\d+학년', r'가족', r'동화',
        r'놀이터', r'인형극', r'안전체험', r'키즈'
    ]
    for pat in kids_keywords:
        if re.search(pat, combined):
            return True

    # 4. '누구나', '전체', '전연령', '연령무관', '제한없음'인 경우: 성인 중심 공지/모임은 제외하고 누구나 참여 가능한 공연/행사/체험 포함
    if re.search(r'(누구나|전체|전\s*연령|연령\s*무관|제한\s*없음|온가족|누구든지)', target):
        if re.search(r'(청소년|성인|시니어|어르신|인문학|재즈|야간|취업|고전|캔들|인문|교수|독서동아리|연합독서회|소설|필사|자격증|생화|자수|미식|테라리움|제스모나이트|화병|지혜학교|사회학|설문조사)', combined):
            return False
        return True

    # 명확한 어린이/누구나 키워드가 없으면 제외
    return False


def matches_age_filter(target_age_group: str, age_filter: Optional[str], raw_target: str = "", title: str = "") -> bool:
    """
    필터(ALL/PRESCHOOL/ELEMENTARY/INFANT/OPEN)에 프로그램이 포함되는지 판정합니다.
    ALL(누구나) 및 FAMILY(가족/보호자 동반) 프로그램은 유아/초등/영아 어떤 필터에서도 함께 노출됩니다.
    또한 대상 텍스트가 유아와 초등을 모두 아우르는 경우(예: 4~9세, 7세~2학년, 6세~초6) 양쪽 필터에 모두 노출합니다.
    """
    if not age_filter or age_filter == "ALL":
        return True
    if age_filter == "OPEN":
        return target_age_group in ("ALL", "FAMILY")
    if target_age_group in ("ALL", "FAMILY"):
        return True
    if target_age_group == age_filter:
        return True

    combined = f"{raw_target or ''} {title or ''}".lower()
    if age_filter == "ELEMENTARY" and target_age_group == "PRESCHOOL":
        return bool(re.search(r'(초등|초\s*[1-6]|(?<!\d)[1-6]학년|(?<!\d)(?:8|9|10|11|12|13)세|201[4-8]년생)', combined))
    if age_filter == "PRESCHOOL" and target_age_group == "ELEMENTARY":
        return bool(re.search(r'(유아|유치|미취학|(?<!\d)[4-7]세|202[0-3]년생)', combined))
    return False


def classify_target_age(raw_target: str, title: str = "") -> Tuple[str, str]:
    """
    대상 텍스트와 제목을 분석하여 표준 연령 카테고리와 친절한 라벨을 반환합니다.
    어린이/가족 외 성인, 시니어, 청소년 등은 EXCLUDE 처리합니다.
    """
    combined = f"{raw_target} {title}".lower()

    # 성인/시니어/청소년 배제
    if not is_kids_program(raw_target, title):
        return "EXCLUDE", "성인/시니어/청소년(제외)"

    # 정규식 패턴 분석 (2026년 기준)
    # 1. 초등학생 명시 키워드 (초등, 초1~6, 학년, 연나이 8~13세, 2014~2019년생)
    has_elem = bool(re.search(r'(초등|초\s*[1-6]|(?<!\d)[1-6]학년|(?<!\d)(?:8|9|10|11|12|13)세|201[4-9]년생)', combined))
    
    # 2. 유아/유치원 (4~7세, 미취학, 2020~2023년생)
    has_preschool = bool(re.search(r'(유아|유치|미취학|(?<!\d)[4-7]세|만\s*[3-5]세|202[0-3]년생)', combined))
    
    # 3. 영아 (0~3세, 개월, 베이비, 북스타트 아가/보물상자)
    has_infant = bool(re.search(r'(영아|(?<!\d)[0-3]세(?!\d)|개월|베이비|북스타트\s*(?:보물상자|아가|플러스)|수유)', combined))
    
    # 4. 가족/보호자 동반
    has_family = bool(re.search(r'(가족|부모\s*동반|보호자\s*동반|아이와\s*함께)', combined))

    # 우선순위 판정:
    # A. 초등학생 키워드가 명시되어 있고 유아/영아가 아닌 경우 -> ELEMENTARY
    if has_elem and not (has_preschool or has_infant):
        return "ELEMENTARY", "초등학생"

    # B. 영아 전용 (0~3세)
    if has_infant and not has_preschool:
        return "INFANT", "영아 (0~3세)"

    # C. 유치원/유아 (4~7세) - 핵심 타겟
    if has_preschool:
        return "PRESCHOOL", "유치원/유아 (4~7세)"

    # D. 유아 키워드는 없지만 초등 키워드가 있는 경우
    if has_elem:
        return "ELEMENTARY", "초등학생"

    # E. 가족 단위
    if has_family:
        return "FAMILY", "가족/보호자 동반"

    # F. 누구나/전체
    if re.search(r'(누구나|전체|전\s*연령|연령\s*무관|제한\s*없음|온가족|누구든지|주민|시민)', combined):
        return "ALL", "누구나"

    return "PRESCHOOL", "유아/어린이"


def classify_day_type(time_info: Optional[str], start_date: Optional[str], end_date: Optional[str], title: str = "") -> Tuple[str, str]:
    """
    행사 요일 및 날짜를 분석하여 주말(토/일)과 평일(월~금)을 구분합니다.
    반환: (WEEKEND / WEEKDAY / ALL, 한글 라벨)
    """
    t_info = (time_info or "").strip()
    combined = f"{t_info} {title}".lower()

    # 1. 텍스트 내 요일 및 주말 키워드 확인
    has_sat = ("토" in t_info) or ("토요" in combined)
    has_sun = ("일 " in t_info) or ("일요" in combined) or t_info.endswith("일") or ("일요일" in combined)
    has_weekend_word = any(k in combined for k in ["주말", "토요", "일요", "화~토", "화-토", "수~토"])

    # 2. 시작일/종료일 요일 체크 (단일 행사일인 경우 특히 유용)
    date_is_weekend = False
    date_is_weekday = False
    try:
        if start_date and re.match(r'^\d{4}-\d{2}-\d{2}$', start_date):
            d1 = datetime.strptime(start_date, '%Y-%m-%d')
            if start_date == end_date or not end_date:
                if d1.weekday() in (5, 6): # 5: 토요일, 6: 일요일
                    date_is_weekend = True
                else:
                    date_is_weekday = True
            else:
                # 기간인 경우: 기간 내에 토/일이 포함되고 time_info에 주말 요일이 있는지 확인
                pass
    except Exception:
        pass

    if has_sat or has_sun or has_weekend_word or date_is_weekend:
        day_sub = []
        if has_sat or (date_is_weekend and d1.weekday() == 5):
            day_sub.append("토")
        if has_sun or (date_is_weekend and d1.weekday() == 6):
            day_sub.append("일")
        sub_str = f"({','.join(day_sub)})" if day_sub else ""
        return "WEEKEND", f"주말{sub_str}" if sub_str else "주말(토/일)"

    # 평일 확인
    has_weekday = any(d in t_info for d in ["월", "화", "수", "목", "금"]) or date_is_weekday
    if has_weekday:
        return "WEEKDAY", "평일(주중)"

    return "ALL", "상시/미정"


def check_is_expired(
    event_start: Optional[str],
    event_end: Optional[str],
    apply_start: Optional[str],
    apply_end: Optional[str],
    status: str,
    title: str = ""
) -> bool:
    """
    행사(교육) 일정이 오늘 이전에 완전히 끝난 강좌인지 판정합니다.
    행사 종료일이 오늘 이후인 경우, 접수가 마감되었더라도 현재 진행 중인 프로그램이므로 만료(is_expired) 처리하지 않습니다.
    """
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    end_date = event_end or event_start

    # 1. 행사 종료일이 명시되어 있는 경우: 행사 종료일이 오늘보다 이전일 때만 만료 처리
    if end_date and len(end_date) >= 10:
        if end_date[:10] < today:
            return True
        return False

    # 2. 행사 종료일 정보가 없는 경우에 한해, 신청 마감일이 지났고 마감된 경우 만료 처리
    if apply_end and len(apply_end) >= 10 and apply_end[:10] < today and status in ("CLOSED", "END"):
        return True

    # 3. 날짜 필드가 모두 없는 공지글의 경우, 제목에 지난 월(예: 11월에 '10월 모집 안내')이 명시되어 있으면 만료 처리
    if not end_date and not apply_end and title:
        month_matches = re.findall(r'(?<!\d)(1[0-2]|[1-9])\s*월', title)
        if month_matches:
            months = [int(m) for m in month_matches]
            # 연말/연초(1~2월 기준 작년 11~12월이 아닌) 단순 지난 달 체크
            if all(1 <= (now.month - m) <= 9 for m in months):
                return True

    return False


def check_is_new(
    apply_start: Optional[str],
    status: str,
    title: str = "",
    is_expired: bool = False,
    first_seen_at: Optional[str] = None,
    now: Optional[datetime] = None,
) -> bool:
    """
    신규 강좌 판정 (자정 기준):
    1) 만료되었거나 마감(CLOSED)된 강좌는 제외
    2) 접수 시작일(apply_start)이 오늘 자정 기준 ±3일([today-3d, today+3d]) 이내이거나
    3) DB 최초 수집 시각(first_seen_at / created_at) + 24시간 이후 끝나는 자정(00:00) 전인 경우
    """
    if is_expired or status == "CLOSED":
        return False

    current = now or datetime.now(KST).replace(tzinfo=None)
    if current.tzinfo is not None:
        current = current.astimezone(KST).replace(tzinfo=None)

    today_date = current.date()
    min_date = today_date - timedelta(days=3)
    max_date = today_date + timedelta(days=3)

    if apply_start and len(apply_start) >= 10:
        try:
            apply_date = datetime.strptime(apply_start[:10], "%Y-%m-%d").date()
            if min_date <= apply_date <= max_date:
                return True
        except ValueError:
            pass

    if first_seen_at:
        try:
            seen_dt = datetime.fromisoformat(first_seen_at.replace("Z", "+00:00"))
            if seen_dt.tzinfo is not None:
                seen_dt = seen_dt.astimezone(KST).replace(tzinfo=None)
            after_24h = seen_dt + timedelta(hours=24)
            if (
                after_24h.hour == 0
                and after_24h.minute == 0
                and after_24h.second == 0
                and after_24h.microsecond == 0
            ):
                expiry_midnight = after_24h
            else:
                expiry_midnight = datetime.combine(
                    after_24h.date() + timedelta(days=1),
                    datetime.min.time(),
                )
            if current < expiry_midnight:
                return True
        except Exception:
            try:
                seen_date = datetime.strptime(first_seen_at[:10], "%Y-%m-%d").date()
                if today_date < seen_date + timedelta(days=2):
                    return True
            except ValueError:
                pass

    return False


def determine_status(raw_status: str, apply_start: Optional[datetime] = None, apply_end: Optional[datetime] = None) -> str:
    """
    접수 상태(APPLY, READY, WAIT, CLOSED) 판정
    날짜/시각 경과 여부를 텍스트 상태보다 우선 반영해, 접수기간이 지난 공고가 대기/접수중으로 남지 않도록 합니다.
    """
    now = datetime.now()
    raw = (raw_status or "").strip()

    # 1. 접수 마감 일시가 명백히 지난 경우 최우선 마감 처리
    if apply_end and now > apply_end:
        return "CLOSED"

    if any(k in raw for k in ["마감", "종료", "완료", "불가"]):
        return "CLOSED"

    # 2. 접수 시작 전이면 접수예정 처리
    if apply_start and now < apply_start:
        return "READY"

    if "대기" in raw:
        return "WAIT"
    if any(k in raw for k in ["접수예정", "예정", "대기중"]):
        return "READY"
    if any(k in raw for k in ["접수중", "신청중", "신청하기", "접수"]):
        return "APPLY"

    if apply_start and apply_end and apply_start <= now <= apply_end:
        return "APPLY"

    return "APPLY"
