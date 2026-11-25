from apscheduler.schedulers.asyncio import AsyncIOScheduler
from crawlers.manager import run_all_crawlers

scheduler = AsyncIOScheduler()


def start_scheduler():
    # 매일 8시, 11시, 14시, 17시 정기 크롤링 (도서관 신규 프로그램 업데이트 시간대)
    scheduler.add_job(run_all_crawlers, "cron", hour="8,11,14,17", minute=0)
    scheduler.start()
    print("[Scheduler] Periodic library crawler scheduled (08:00, 11:00, 14:00, 17:00)")


def stop_scheduler():
    scheduler.shutdown()
