import asyncio
from fastapi import FastAPI, BackgroundTasks, Query, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
import urllib.parse
from database import init_db, query_programs, get_library_stats, get_crawler_logs
from crawlers.manager import run_all_crawlers
from export_static import sync_github_pages, should_auto_sync_on_startup, get_last_sync_info, write_static_files
from models import BookmarkletProfile

from scheduler import start_scheduler, stop_scheduler

# Lifespan event to init DB, start scheduler and run startup crawl/sync in background
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    progs = query_programs()
    if len(progs) == 0:
        print("[Startup] Database empty. Running initial crawl + GitHub sync...")
        await sync_github_pages(crawl=True, reason="startup_empty")
    elif should_auto_sync_on_startup(min_age_minutes=30):
        print("[Startup] Scheduling background crawl + GitHub sync...")
        asyncio.create_task(sync_github_pages(crawl=True, reason="startup"))
    yield
    stop_scheduler()

app = FastAPI(
    title="위례키즈 도서관 API",
    description="송파, 하남, 성남 위례 도서관 어린이 체험 프로그램 수집 및 예약 보조 백엔드",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "wirye-kids-library-backend"}


@app.get("/api/programs")
def get_programs(
    region: Optional[str] = Query(None, description="송파, 하남, 성남 또는 ALL"),
    library: Optional[str] = Query(None, description="특정 도서관명 또는 ALL"),
    age_group: Optional[str] = Query(None, description="PRESCHOOL, INFANT, ELEMENTARY, OPEN(누구나/가족), ALL(전체)"),
    day_type: Optional[str] = Query(None, description="WEEKEND, WEEKDAY, ALL"),
    status: Optional[str] = Query(None, description="APPLY, READY, WAIT, CLOSED 또는 ALL"),
    search: Optional[str] = Query(None, description="검색어 (제목, 대상 등)"),
    include_expired: bool = Query(False, description="마감/종료된 지난 프로그램 포함 여부 (기본: 제외)")
):
    results = query_programs(
        region=region,
        library=library,
        age_group=age_group,
        day_type=day_type,
        status=status,
        search=search,
        include_expired=include_expired
    )
    return {
        "count": len(results),
        "programs": results
    }


@app.get("/api/stats")
def get_stats():
    library_stats = get_library_stats()
    all_programs = query_programs(include_expired=True)
    # 실제 신청 가능한 활성 프로그램 (만료되지 않고 접수 마감되지 않은 건)
    active_programs = [p for p in all_programs if not p.get("is_expired") and p.get("status") != "CLOSED"]
    
    total = len(all_programs)
    active_total = len(active_programs)
    new_count = sum(1 for p in active_programs if p.get("is_new"))
    expired_count = total - active_total  # 마감 및 만료된 강좌 전체 합계

    preschool_count = sum(1 for p in active_programs if p.get("target_age_group") == "PRESCHOOL")
    infant_count = sum(1 for p in active_programs if p.get("target_age_group") == "INFANT")
    elementary_count = sum(1 for p in active_programs if p.get("target_age_group") == "ELEMENTARY")
    family_count = sum(1 for p in active_programs if p.get("target_age_group") == "FAMILY")
    all_age_count = sum(1 for p in active_programs if p.get("target_age_group") in ("ALL", "FAMILY"))
    apply_count = sum(1 for p in active_programs if p.get("status") == "APPLY")
    ready_count = sum(1 for p in active_programs if p.get("status") == "READY")
    weekend_count = sum(1 for p in active_programs if p.get("day_type") == "WEEKEND")
    weekday_count = sum(1 for p in active_programs if p.get("day_type") == "WEEKDAY")

    crawler_logs = get_crawler_logs()

    return {
        "total": total,
        "active_total": active_total,
        "new_count": new_count,
        "expired_count": expired_count,
        "preschool_count": preschool_count,
        "infant_count": infant_count,
        "elementary_count": elementary_count,
        "family_count": family_count,
        "all_age_count": all_age_count,
        "apply_count": apply_count,
        "ready_count": ready_count,
        "weekend_count": weekend_count,
        "weekday_count": weekday_count,
        "library_stats": library_stats,
        "crawler_logs": crawler_logs
    }


async def _refresh_local_only():
    summary = await run_all_crawlers()
    write_static_files(summary=summary)


@app.post("/api/refresh")
async def trigger_refresh(background_tasks: BackgroundTasks):
    """
    수동 크롤링 새로고침 트리거
    """
    background_tasks.add_task(_refresh_local_only)
    return {"message": "크롤링 작업이 백그라운드에서 시작되었습니다."}


@app.get("/api/sync-github/status")
def sync_github_status(request: Request):
    client_host = request.client.host if request.client else ""
    if client_host not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(status_code=403, detail="로컬 환경에서만 조회 가능합니다.")
    return get_last_sync_info()


@app.post("/api/sync-github")
async def sync_github_endpoint(request: Request, crawl: bool = Query(True, description="동기화 전 최신 크롤링 실행 여부")):
    """
    로컬 위키즈 화면 전용: 최신 데이터를 수집해 GitHub Pages 저장소로 즉시 커밋/푸시합니다.
    """
    client_host = request.client.host if request.client else ""
    if client_host not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(status_code=403, detail="로컬 환경에서만 동기화를 실행할 수 있습니다.")
    result = await sync_github_pages(crawl=crawl, reason="manual_ui")
    return result


@app.post("/api/bookmarklet/generate")
def generate_bookmarklet(profile: BookmarkletProfile):
    """
    자녀 프로필 정보를 주입하는 브라우저 북마클릿 JavaScript 코드 생성
    """
    clean_birth = profile.birth_date.replace("-", "").replace(".", "")
    clean_phone = profile.phone_number.replace("-", "").strip()

    # Split phone into 3 parts
    p1 = "010"
    p2 = ""
    p3 = ""
    if len(clean_phone) == 11:
        p1, p2, p3 = clean_phone[:3], clean_phone[3:7], clean_phone[7:]
    elif len(clean_phone) == 10:
        p1, p2, p3 = clean_phone[:3], clean_phone[3:6], clean_phone[6:]

    js_code = f"""javascript:(function(){{
    var childName = {repr(profile.child_name)};
    var parentName = {repr(profile.parent_name)};
    var birthFull = {repr(profile.birth_date)};
    var birthClean = {repr(clean_birth)};
    var phoneFull = {repr(profile.phone_number)};
    var p1 = {repr(p1)}, p2 = {repr(p2)}, p3 = {repr(p3)};
    var gender = {repr(profile.gender)};

    var filledCount = 0;

    /* 1. 성명 / 신청자 / 자녀명 채우기 */
    var nameSelectors = [
        "input[name*='name']", "input[id*='name']", "input[name*='applcnt']",
        "input[name*='studnt']", "input[name*='child']", "input[name*='user_nm']"
    ];
    document.querySelectorAll(nameSelectors.join(',')).forEach(function(el){{
        if (el.type === 'text' || el.type === 'search') {{
            var idOrName = (el.name + ' ' + el.id).toLowerCase();
            if (idOrName.indexOf('parent') !== -1 || idOrName.indexOf('prnt') !== -1) {{
                el.value = parentName;
            }} else {{
                el.value = childName;
            }}
            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            filledCount++;
        }}
    }});

    /* 2. 생년월일 채우기 */
    var birthSelectors = ["input[name*='birth']", "input[id*='birth']", "input[name*='brthdy']"];
    document.querySelectorAll(birthSelectors.join(',')).forEach(function(el){{
        el.value = (el.maxLength === 8) ? birthClean : birthFull;
        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
        filledCount++;
    }});

    /* 3. 연락처 채우기 */
    var phoneSelectors = ["input[name*='tel']", "input[name*='phone']", "input[name*='mbtlnum']", "input[name*='hp']"];
    var phoneInputs = Array.from(document.querySelectorAll(phoneSelectors.join(','))).filter(function(el){{
        return el.type === 'text' || el.type === 'tel' || el.type === 'number';
    }});

    if (phoneInputs.length >= 3) {{
        phoneInputs[0].value = p1;
        phoneInputs[1].value = p2;
        phoneInputs[2].value = p3;
        phoneInputs.forEach(function(el){{
            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }});
        filledCount += 3;
    }} else if (phoneInputs.length === 1) {{
        phoneInputs[0].value = phoneFull;
        phoneInputs[0].dispatchEvent(new Event('input', {{ bubbles: true }}));
        phoneInputs[0].dispatchEvent(new Event('change', {{ bubbles: true }}));
        filledCount++;
    }}

    /* 4. 개인정보 수집/이용 동의 체크박스 자동 선택 */
    var checkboxes = document.querySelectorAll("input[type='checkbox']");
    checkboxes.forEach(function(chk){{
        var parentTxt = (chk.parentElement ? chk.parentElement.innerText : '').toLowerCase();
        var chkId = (chk.id + ' ' + chk.name).toLowerCase();
        if (parentTxt.indexOf('동의') !== -1 || chkId.indexOf('agree') !== -1 || chkId.indexOf('chk') !== -1) {{
            chk.checked = true;
            chk.dispatchEvent(new Event('change', {{ bubbles: true }}));
            filledCount++;
        }}
    }});

    /* 5. 성별 라디오 버튼 선택 */
    var genderRadios = document.querySelectorAll("input[type='radio'][value*='" + gender + "'], input[type='radio'][id*='" + (gender === 'M' ? 'male' : 'female') + "']");
    genderRadios.forEach(function(r){{
        r.checked = true;
        r.dispatchEvent(new Event('change', {{ bubbles: true }}));
    }});

    /* 피드백 안내 */
    var toast = document.createElement('div');
    toast.innerHTML = '⚡ <b>[위례키즈 부스터]</b> 자녀 정보(' + childName + ') 자동 입력 및 약관 동의 완료 (' + filledCount + '개 항목)';
    toast.style.cssText = 'position:fixed;top:20px;left:50%;transform:translateX(-50%);background:#10b981;color:#fff;padding:14px 24px;border-radius:12px;font-size:15px;font-weight:bold;z-index:999999;box-shadow:0 8px 24px rgba(0,0,0,0.2);animation:fadeIn 0.3s;';
    document.body.appendChild(toast);
    setTimeout(function(){{ toast.remove(); }}, 3500);
}})();"""

    # URL encode for href
    bookmarklet_url = js_code.replace("\n", " ").strip()

    return {
        "bookmarklet_url": bookmarklet_url,
        "clean_birth": clean_birth,
        "clean_phone": clean_phone
    }
