from apscheduler.schedulers.asyncio import AsyncIOScheduler
from export_static import sync_github_pages

scheduler = AsyncIOScheduler()


async def _scheduled_crawl_and_sync():
    await sync_github_pages(crawl=True, reason="schedule")


def start_scheduler():
    # 매일 8시, 11시, 14시, 17시 정기 크롤링 + 변경 시 GitHub 자동 동기화
    scheduler.add_job(_scheduled_crawl_and_sync, "cron", hour="8,11,14,17", minute=0)
    scheduler.start()
    print("[Scheduler] Periodic library crawler + GitHub sync scheduled (08:00, 11:00, 14:00, 17:00)")


def stop_scheduler():
    scheduler.shutdown()
