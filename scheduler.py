import json
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from croniter import croniter
from dotenv import load_dotenv
from loguru import logger

import get_cookie


STOP = False
STATE = {
    "started_at": datetime.now().isoformat(timespec="seconds"),
    "last_run_at": None,
    "last_exit_code": None,
    "status": "starting",
}


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ["/", "/health", "/healthz"]:
            self.send_response(404)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": "not found"}).encode("utf-8"))
            return

        payload = {
            "ok": True,
            "service": "auto_deploy",
            "status": STATE["status"],
            "started_at": STATE["started_at"],
            "last_run_at": STATE["last_run_at"],
            "last_exit_code": STATE["last_exit_code"],
            "now": datetime.now().isoformat(timespec="seconds"),
        }
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def log_message(self, format, *args):
        logger.debug("health server - {}", format % args)


def start_health_server():
    port = int(os.getenv("PORT", "7860"))
    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Health server listening on 0.0.0.0:{}", port)
    return server


def handle_signal(signum, frame):
    global STOP
    STOP = True
    STATE["status"] = "stopping"
    logger.warning("Received signal {}, exiting", signum)


def run_job():
    STATE["status"] = "running"
    STATE["last_run_at"] = datetime.now().isoformat(timespec="seconds")
    logger.info("Running auto_redeploy.py at {}", STATE["last_run_at"])
    result = subprocess.run([sys.executable, "auto_redeploy.py"], check=False)
    STATE["last_exit_code"] = result.returncode
    STATE["status"] = "idle" if result.returncode == 0 else "error"
    if result.returncode != 0:
        logger.error("Job exited with code {}", result.returncode)
    else:
        logger.success("Job finished successfully")


def sleep_until(target_timestamp):
    while not STOP:
        remaining = target_timestamp - time.time()
        if remaining <= 0:
            return
        time.sleep(min(remaining, 1))


def main():
    logger.remove()
    logger.add(sys.stdout, level=os.getenv("LOG_LEVEL", "INFO"))

    load_dotenv(override=True)
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    health_server = start_health_server()

    cookie = os.getenv("BACK4APP_COOKIE", "").strip()
    if not cookie:
        logger.info("Refreshing cookie on startup")
        get_cookie.main()

    load_dotenv(override=True)
    schedule = os.getenv("CRON_SCHEDULE", "*/1 * * * *").strip()
    run_on_startup = os.getenv("RUN_ON_STARTUP", "false").strip().lower() in {"1", "true", "yes", "on"}

    try:
        cron = croniter(schedule, datetime.now())
    except Exception as exc:
        health_server.shutdown()
        raise RuntimeError(f"CRON_SCHEDULE invalid: {schedule} ({exc})") from exc

    logger.info("Scheduler started, cron={}", schedule)
    STATE["status"] = "idle"

    if run_on_startup:
        run_job()

    while not STOP:
        next_run = cron.get_next(datetime)
        logger.info("Next run at {}", next_run.isoformat(timespec="seconds"))
        sleep_until(next_run.timestamp())
        if STOP:
            break
        run_job()

    health_server.shutdown()
    logger.info("Scheduler stopped")


if __name__ == "__main__":
    main()
