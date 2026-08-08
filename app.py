"""Dashboard for tracking multiple Google Careers job listings until their Apply button appears."""

import os
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, url_for

import store
from job_checker import fetch_job
from notifier import notify

load_dotenv()

POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL_SECONDS", "300"))
NTFY_TOPIC = os.environ.get("NTFY_TOPIC")
NTFY_SERVER = os.environ.get("NTFY_SERVER")

app = Flask(__name__)
store.init_db()


def check_one_job(job_id: int, url: str) -> None:
    try:
        result = fetch_job(url)
    except Exception as exc:
        store.mark_checked(job_id, title=None, error=str(exc))
        return

    store.mark_checked(job_id, title=result["title"], error=None)

    if result["apply_url"]:
        store.mark_found(job_id, result["apply_url"])
        notify(
            f'Apply button is live for "{result["title"]}"! {result["apply_url"]}',
            title=f'Apply is live: {result["title"]}',
            click_url=result["apply_url"],
        )


def poll_all_waiting_jobs() -> None:
    for job in store.waiting_jobs():
        check_one_job(job["id"], job["url"])


scheduler = BackgroundScheduler()
scheduler.add_job(poll_all_waiting_jobs, "interval", seconds=POLL_INTERVAL_SECONDS)
scheduler.start()


@app.template_filter("friendly_time")
def friendly_time(value):
    if not value:
        return None
    dt = datetime.fromisoformat(value).astimezone()
    return dt.strftime("%b %d, %Y %I:%M %p").replace(" 0", " ")


@app.route("/")
def dashboard():
    return render_template("dashboard.html", jobs=store.list_jobs(), interval=POLL_INTERVAL_SECONDS)


@app.route("/jobs", methods=["POST"])
def add_job():
    url = request.form.get("url", "").strip()
    if url:
        try:
            job_id = store.add_job(url)
        except Exception:
            pass  # duplicate URL or similar — ignore and just show the list
        else:
            check_one_job(job_id, url)
    return redirect(url_for("dashboard"))


@app.route("/jobs/<int:job_id>/delete", methods=["POST"])
def delete_job(job_id):
    store.delete_job(job_id)
    return redirect(url_for("dashboard"))


@app.route("/jobs/<int:job_id>/check", methods=["POST"])
def check_job(job_id):
    job = store.get_job(job_id)
    if job and job["status"] == "waiting":
        check_one_job(job_id, job["url"])
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    # Kick off an immediate poll so freshly added jobs don't wait a full interval.
    scheduler.add_job(poll_all_waiting_jobs, "date")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
