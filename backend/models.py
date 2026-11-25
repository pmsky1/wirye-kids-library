from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class Program(BaseModel):
    id: str
    source: str                          # SONGPA, HANAM, SEONGNAM
    library_name: str                    # 송파위례도서관, 하남위례도서관, 성남위례도서관, 송파글마루도서관 등
    region: str                          # 송파, 하남, 성남
    title: str
    target_age_group: str                # PRESCHOOL, INFANT, ELEMENTARY, FAMILY, ALL, ADULT, OTHER
    target_label: str                    # 유치원/유아 (4~7세), 초등 저학년, 영아 등
    target_raw: str                      # 원본 대상 표기 텍스트
    day_type: str = "ALL"                # WEEKEND(주말), WEEKDAY(평일), ALL(상시/전체)
    day_label: str = "상시/미정"         # 주말(토/일), 평일(주중) 등
    is_new: bool = False                 # 최근 신규 등록/업데이트 여부
    is_expired: bool = False             # 신청/일정 마감 및 종료 여부
    fee: str = "무료"
    capacity: Optional[str] = None       # 신청 현황 (예: 7/10명, 대기 0명)
    apply_start: Optional[str] = None    # YYYY-MM-DD HH:MM
    apply_end: Optional[str] = None      # YYYY-MM-DD HH:MM
    event_start: Optional[str] = None    # YYYY-MM-DD
    event_end: Optional[str] = None      # YYYY-MM-DD
    event_time_info: Optional[str] = None# 매주 수 15:00 ~ 16:20 등
    location: Optional[str] = None       # 강의실 위치
    status: str                          # APPLY(접수중), READY(접수예정), WAIT(대기접수), CLOSED(마감)
    status_label: str                    # 접수중, 접수예정, 대기접수, 마감
    detail_url: str                      # 상세/신청 안내 페이지 URL
    apply_url: Optional[str] = None      # 원클릭 신청 폼 URL (있을 경우)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class BookmarkletProfile(BaseModel):
    child_name: str
    birth_date: str                      # YYYY-MM-DD or YYYYMMDD
    gender: str = "M"                    # M / F
    parent_name: str
    phone_number: str                    # 010-XXXX-XXXX
    email: Optional[str] = ""
    address: Optional[str] = ""
