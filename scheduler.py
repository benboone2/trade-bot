"""
Automated scheduler — runs signal scans and order syncs on a fixed schedule.
Designed to run continuously as a background process.

Run with: python scheduler.py

Schedule (all times Eastern):
  09:35  Mon–Fri  Morning scan — evaluate signals, place orders
  */5    09–15    Sync fills every 5 min during market hours
  15:55  Mon–Fri  End-of-day report + final sync
"""

import logging
from datetime import datetime

import pytz
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

load_dotenv()

from jobs import build_components, is_market_open, print_eod_report, run_signal_scan, run_sync

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

ET = pytz.timezone("America/New_York")

# Initialize once — all jobs share these instances
connector, risk, oms, engine = build_components()


# ------------------------------------------------------------------
# Jobs
# ------------------------------------------------------------------

def job_morning_scan():
    log.info("=== Morning scan ===")
    try:
        run_signal_scan(connector, risk, oms, engine, execute=True)
    except Exception as e:
        log.error(f"Morning scan failed: {e}", exc_info=True)


def job_sync_fills():
    try:
        updated = run_sync(oms)
        if updated:
            log.info(f"Sync: {updated} order(s) updated")
    except Exception as e:
        log.error(f"Sync failed: {e}", exc_info=True)


def job_eod_report():
    log.info("=== End-of-day report ===")
    try:
        run_sync(oms)
        print_eod_report(oms, risk)
    except Exception as e:
        log.error(f"EOD report failed: {e}", exc_info=True)


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():
    scheduler = BlockingScheduler(timezone=ET)

    # Morning signal scan — 9:35am ET, weekdays only
    scheduler.add_job(
        job_morning_scan,
        CronTrigger(hour=9, minute=35, day_of_week="mon-fri", timezone=ET),
        id="morning_scan",
        name="Morning signal scan",
    )

    # Sync fills every 5 minutes during market hours (9:30am–4:00pm ET)
    scheduler.add_job(
        job_sync_fills,
        CronTrigger(minute="*/5", hour="9-15", day_of_week="mon-fri", timezone=ET),
        id="sync_fills",
        name="Sync order fills",
    )

    # End-of-day report at 3:55pm ET
    scheduler.add_job(
        job_eod_report,
        CronTrigger(hour=15, minute=55, day_of_week="mon-fri", timezone=ET),
        id="eod_report",
        name="End-of-day report",
    )

    now_et = datetime.now(ET)
    log.info(f"Scheduler started — current time: {now_et.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    log.info("Jobs scheduled:")
    for job in scheduler.get_jobs():
        nrt = getattr(job, "next_run_time", None)
        next_run = nrt.strftime("%Y-%m-%d %H:%M:%S %Z") if nrt else "pending"
        log.info(f"  {job.name}: next run {next_run}")
    log.info("Press Ctrl+C to stop.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
