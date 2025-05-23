# Job wrapper for scheduled recordings
def job_wrapper(filename, duration, **kwargs):
    run_time = datetime.now().strftime("%Y%m%d_%H%M")
    dated_filename = f"{filename.rstrip('.wav')}_{run_time}.wav"
    print(f"[{datetime.now()}] Firing job: {dated_filename} for {duration} seconds")
    print("Recording job triggered.")
    threading.Thread(target=record_audio, args=(dated_filename, duration)).start()

from flask import Flask, request, jsonify, render_template, redirect, url_for, send_file, flash
import subprocess
import os
import alsaaudio
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from datetime import datetime, timedelta, timezone
import threading
import json

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "streammanager-default-key")
DARKICE_CONFIG_PATH = "/etc/darkice/darkice.cfg"
RECORDINGS_DIR = "/opt/StreamManager/recordings"
os.makedirs(RECORDINGS_DIR, exist_ok=True)


scheduler = BackgroundScheduler(
    jobstores={'default': MemoryJobStore()},
    executors={'default': ThreadPoolExecutor(10)},
    timezone="UTC"
)
scheduler.start()
print("Scheduler started:", scheduler.running)

# Reload scheduled jobs from JSON
schedule_file = "/opt/StreamManager/schedule.json"
if os.path.exists(schedule_file):
    try:
        with open(schedule_file, "r") as f:
            stored_jobs = json.load(f)
        for job in stored_jobs:
            job_id = job["id"]
            filename = job["filename"]
            start_time = datetime.fromisoformat(job["start_time"]).astimezone(timezone.utc)
            end_time = datetime.fromisoformat(job["end_time"]).astimezone(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            recurrence = job.get("recurrence", "once")
            job_kwargs = {"filename": filename, "duration": duration, "start": start_time, "end": end_time}

            if recurrence == "once":
                if start_time > datetime.now(timezone.utc):
                    scheduler.add_job(job_wrapper, trigger="date", run_date=start_time, id=job_id,
                                      kwargs=job_kwargs, timezone=timezone.utc)
            elif recurrence == "daily":
                scheduler.add_job(job_wrapper, trigger=CronTrigger(hour=start_time.hour, minute=start_time.minute, timezone=timezone.utc),
                                  id=job_id, replace_existing=True, kwargs=job_kwargs)
            elif recurrence == "weekly":
                dow_str = start_time.strftime("%a").lower()
                scheduler.add_job(job_wrapper, trigger=CronTrigger(day_of_week=dow_str, hour=start_time.hour, minute=start_time.minute, timezone=timezone.utc),
                                  id=job_id, replace_existing=True, kwargs=job_kwargs)
            elif recurrence == "monthly":
                scheduler.add_job(job_wrapper, trigger=CronTrigger(day=start_time.day, hour=start_time.hour, minute=start_time.minute, timezone=timezone.utc),
                                  id=job_id, replace_existing=True, kwargs=job_kwargs)
            elif recurrence == "yearly":
                scheduler.add_job(job_wrapper, trigger=CronTrigger(month=start_time.month, day=start_time.day, hour=start_time.hour, minute=start_time.minute, timezone=timezone.utc),
                                  id=job_id, replace_existing=True, kwargs=job_kwargs)
            print(f"[RESTORE] Job loaded: {job_id} (recurrence: {recurrence})")
    except Exception as e:
        print(f"[ERROR] Failed to reload schedule: {e}")

# Dashboard route
@app.route("/")
def dashboard():
    darkice_status = check_service_status("darkice")
    jobs = scheduler.get_jobs()
    now = datetime.now(timezone.utc)

    upcoming = None
    active_recording = is_recording_active()

    for job in jobs:
        if "recording_" in job.id:
            if job.next_run_time and job.next_run_time > now:
                upcoming = job.next_run_time

    schedule_file = "/opt/StreamManager/schedule.json"
    scheduled_jobs = []
    if os.path.exists(schedule_file):
        try:
            with open(schedule_file, "r") as f:
                all_jobs = json.load(f)

            now_utc = datetime.now(timezone.utc)
            scheduled_jobs = []
            for job in all_jobs:
                if job.get("recurrence") == "once":
                    start = datetime.fromisoformat(job["start_time"]).astimezone(timezone.utc)
                    if start > now_utc:
                        scheduled_jobs.append(job)
                else:
                    scheduled_jobs.append(job)

            with open(schedule_file, "w") as f:
                json.dump(scheduled_jobs, f, indent=2)
        except Exception as e:
            print(f"Failed to load or update scheduled jobs: {e}")

    return render_template(
        "index.html",
        darkice_status=darkice_status,
        upcoming_recording=upcoming,
        recording_active=active_recording,
        scheduled_jobs=scheduled_jobs
    )

# Helper function to check service status
def check_service_status(service_name):
    try:
        result = subprocess.run(
            ["systemctl", "is-active", service_name],
            capture_output=True,
            text=True
        )
        return result.stdout.strip()
    except Exception as e:
        return f"Error checking status: {e}"

# Restart DarkIce
@app.route("/darkice/restart", methods=["POST"])
def restart_darkice():
    try:
        subprocess.run(["sudo", "systemctl", "restart", "darkice"], check=True)
        return jsonify({"status": "success", "message": "DarkIce restarted successfully"})
    except subprocess.CalledProcessError:
        return jsonify({"status": "error", "message": "Failed to restart DarkIce"})

# Edit DarkIce Configuration
@app.route("/darkice/edit", methods=["GET", "POST"])
def edit_darkice():
    if request.method == "POST":
        config_content = request.form.get("config")
        try:
            with open(DARKICE_CONFIG_PATH, "w", encoding="ascii", errors="ignore", newline="\n") as config_file:
              config_file.write(config_content)
            return redirect(url_for("dashboard"))
        except Exception as e:
            return f"Failed to save configuration: {e}"
    else:
        try:
            with open(DARKICE_CONFIG_PATH, "r") as config_file:
                config_content = config_file.read()
        except FileNotFoundError:
            config_content = "Configuration file not found."
        return render_template("edit_darkice.html", config=config_content)

# ALSA Control    
@app.route("/alsa/manage", methods=["GET", "POST"])
def manage_alsa():
    try:
        mixer = alsaaudio.Mixer(control='Mic', cardindex=1)  # Initialize mixer for input device volume control
    except alsaaudio.ALSAAudioError:
        mixer = None

    if request.method == "POST":
        # Handle device selection
        playback_device = request.form.get("playback_device")
        mic_device = request.form.get("mic_device")

        # Handle volume adjustment
        if "volume" in request.form and mixer:
            try:
                volume = int(request.form.get("volume"))
                print(f"Setting input volume to {volume}")
                mixer.setrec(1)  # Enable capture
                subprocess.run(["amixer", "-c", "1", "sset", "Mic", f"{volume}%", "cap"], check=True)
            except Exception as e:
                print(f"Error setting input volume: {e}")

        try:
            # Save selected devices to a config file or apply immediately
            with open("/opt/StreamManager/alsa_devices.cfg", "w") as device_file:
                device_file.write(f"playback_device={playback_device}\n")
                device_file.write(f"mic_device={mic_device}\n")
            # (Restarting DarkIce removed here)
            return redirect(url_for("manage_alsa"))
        except Exception as e:
            return f"Failed to update devices: {e}"

    else:
        # Retrieve available ALSA devices
        cards = alsaaudio.cards()
        mixers = alsaaudio.mixers()

        # Get current volume
        current_volume = mixer.getvolume()[0] if mixer else None

        # Load current selections from the config file
        playback_device, mic_device = None, None
        try:
            with open("/opt/StreamManager/alsa_devices.cfg", "r") as device_file:
                for line in device_file:
                    if "playback_device=" in line:
                        playback_device = line.strip().split("=")[1]
                    if "mic_device=" in line:
                        mic_device = line.strip().split("=")[1]
        except FileNotFoundError:
            pass  # Config file doesn't exist yet

        return render_template(
            "manage_alsa.html",
            cards=cards,
            mixers=mixers,
            playback_device=playback_device,
            mic_device=mic_device,
            volume=current_volume,
        )

# Reboot system
@app.route("/reboot", methods=["POST"])
def reboot_system():
    try:
        subprocess.run(["sudo", "reboot"], check=True)
        return jsonify({"status": "success", "message": "System rebooting..."})
    except subprocess.CalledProcessError as e:
        return jsonify({"status": "error", "message": f"Failed to reboot: {str(e)}"})

# Recording job function
def record_audio(filename, duration_seconds):
    filepath = os.path.join(RECORDINGS_DIR, filename)
    command = [
        "ffmpeg",
        "-f", "alsa",
        "-i", "shared_input",
        "-t", str(duration_seconds),
        "-acodec", "pcm_s16le",
        "-ar", "44100",
        filepath
    ]
    print("Running ffmpeg command:", " ".join(command))
    try:
        result = subprocess.run(command, check=True, stderr=subprocess.PIPE, text=True)
        print("Recording completed:", filepath)
    except subprocess.CalledProcessError as e:
        print(f"Recording failed: {e}")
        print("stderr:", e.stderr)

# Schedule a recording
@app.route("/recordings/schedule", methods=["POST"])
def schedule_recording():
    data = request.get_json()
    print(f"[DEBUG] Incoming schedule request: {data}")
    start_time_str = data.get("start_time")
    end_time_str = data.get("end_time")
    filename = data.get("filename")
    recurrence = data.get("recurrence", "once")

    if not start_time_str or not end_time_str or not filename:
        flash("Missing required fields", "error")
        return redirect(url_for("new_recording_form"))

    try:
        start_time = datetime.fromisoformat(start_time_str).astimezone(timezone.utc)
        end_time = datetime.fromisoformat(end_time_str).astimezone(timezone.utc)
        duration = (end_time - start_time).total_seconds()
        if duration <= 0:
            flash("End time must be after start time", "error")
            return redirect(url_for("new_recording_form"))

        job_id = f"recording_{filename}_{start_time.timestamp()}"

        job_kwargs = {"filename": filename, "duration": duration, "start": start_time, "end": end_time}

        if recurrence == "once":
            scheduler.add_job(job_wrapper, trigger="date", run_date=start_time, id=job_id,
                              kwargs=job_kwargs, timezone=timezone.utc)
        elif recurrence == "daily":
            scheduler.add_job(job_wrapper, trigger=CronTrigger(hour=start_time.hour, minute=start_time.minute, timezone=timezone.utc),
                              id=job_id, replace_existing=True, kwargs=job_kwargs)
        elif recurrence == "weekly":
            dow_str = start_time.strftime("%a").lower()  # e.g. "mon"
            scheduler.add_job(job_wrapper, trigger=CronTrigger(day_of_week=dow_str, hour=start_time.hour, minute=start_time.minute, timezone=timezone.utc),
                              id=job_id, replace_existing=True, kwargs=job_kwargs)
        elif recurrence == "monthly":
            scheduler.add_job(job_wrapper, trigger=CronTrigger(day=start_time.day, hour=start_time.hour, minute=start_time.minute, timezone=timezone.utc),
                              id=job_id, replace_existing=True, kwargs=job_kwargs)
        elif recurrence == "yearly":
            scheduler.add_job(job_wrapper, trigger=CronTrigger(month=start_time.month, day=start_time.day, hour=start_time.hour, minute=start_time.minute, timezone=timezone.utc),
                              id=job_id, replace_existing=True, kwargs=job_kwargs)
        else:
            flash("Invalid recurrence option", "error")
            return redirect(url_for("new_recording_form"))

        print(f"[DEBUG] Job added: {job_id} (recurrence: {recurrence}) at {start_time}")
        print(f"[DEBUG] Total jobs in scheduler: {len(scheduler.get_jobs())}")
        for job in scheduler.get_jobs():
            print(f" - {job.id} -> Next run: {job.next_run_time}")

        print(f"Job scheduled: {job_id} → starts at {start_time} for {duration}s")

        # Save schedule metadata
        schedule_file = "/opt/StreamManager/schedule.json"
        schedule_entry = {
            "id": job_id,
            "filename": filename,
            "start_time": start_time_str,
            "end_time": end_time_str,
            "recurrence": recurrence
        }
        try:
            if os.path.exists(schedule_file):
                with open(schedule_file, "r") as f:
                    schedule_data = json.load(f)
            else:
                schedule_data = []

            # Remove expired one-time jobs
            schedule_data = [
                s for s in schedule_data
                if s.get("recurrence") != "once" or datetime.fromisoformat(s["start_time"]).astimezone(timezone.utc) > datetime.now(timezone.utc)
            ]

            # Replace existing entry with same id if it exists
            schedule_data = [s for s in schedule_data if s["id"] != job_id]
            schedule_data.append(schedule_entry)

            with open(schedule_file, "w") as f:
                json.dump(schedule_data, f, indent=2)
        except Exception as e:
            print("Failed to write schedule file:", e)

        flash("Recording scheduled successfully", "success")
        return redirect(url_for("dashboard"))
    except Exception as e:
        flash(f"Failed to schedule recording: {e}", "error")
        return redirect(url_for("new_recording_form"))

# List recordings
@app.route("/recordings", methods=["GET"])
def list_recordings():
    try:
        files = os.listdir(RECORDINGS_DIR)
        recordings = []
        for f in files:
            if f.lower().endswith(".wav"):
                path = os.path.join(RECORDINGS_DIR, f)
                size_kb = os.path.getsize(path) // 1024
                modified_time = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%b %d, %Y %I:%M %p")
                recordings.append({"name": f, "size": size_kb, "modified": modified_time})
        return render_template("recordings.html", recordings=recordings)
    except Exception as e:
        return render_template("recordings.html", recordings=[], error=str(e))

@app.route("/recordings/scheduled", methods=["GET"])
def scheduled_recordings():
    jobs = scheduler.get_jobs()
    job_list = []
    for job in jobs:
        if "recording_" in job.id:
            job_list.append({
                "id": job.id,
                "next_run": job.next_run_time.strftime("%b %d, %Y %I:%M %p") if job.next_run_time else "N/A"
            })
    return jsonify(job_list)

# Download individual recording
@app.route("/recordings/download/<filename>")
def download_recording(filename):
    path = os.path.join(RECORDINGS_DIR, filename)
    if os.path.isfile(path):
        return send_file(path, as_attachment=True)
    return "File not found", 404

# Serve form to schedule new recording
@app.route("/recordings/new", methods=["GET"])
def new_recording_form():
    schedule_file = "/opt/StreamManager/schedule.json"
    scheduled_jobs = []
    if os.path.exists(schedule_file):
        try:
            with open(schedule_file, "r") as f:
                scheduled_jobs = json.load(f)
        except Exception as e:
            print(f"Failed to load scheduled jobs: {e}")
    return render_template("new_recording.html", scheduled_jobs=scheduled_jobs)

def is_recording_active():
    now = datetime.now(timezone.utc)
    for job in scheduler.get_jobs():
        if "recording_" in job.id:
            start = job.kwargs.get("start")
            end = job.kwargs.get("end")
            if start and end:
                if start <= now <= end:
                    return True
            else:
                # Fallback: estimate duration from job metadata
                if job.next_run_time:
                    estimated_start = job.next_run_time
                    estimated_end = estimated_start + timedelta(seconds=job.kwargs.get("duration", 60))
                    if estimated_start <= now <= estimated_end:
                        return True
    return False


# Delete a scheduled recording by job ID
@app.route("/recordings/delete-schedule/<job_id>", methods=["POST"])
def delete_schedule(job_id):
    try:
        scheduler.remove_job(job_id)
    except Exception as e:
        print(f"[ERROR] Failed to remove scheduler job: {e}")

    # Remove from schedule.json
    schedule_file = "/opt/StreamManager/schedule.json"
    if os.path.exists(schedule_file):
        try:
            with open(schedule_file, "r") as f:
                data = json.load(f)
            data = [s for s in data if s["id"] != job_id]
            with open(schedule_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[ERROR] Failed to update schedule.json: {e}")

    flash("Schedule deleted", "success")
    return redirect(url_for("new_recording_form"))


# Delete a recording file by filename
@app.route("/recordings/delete/<filename>", methods=["POST"])
def delete_recording(filename):
    path = os.path.join(RECORDINGS_DIR, filename)
    try:
        os.remove(path)
        flash(f"Deleted {filename}", "success")
    except Exception as e:
        flash(f"Failed to delete {filename}: {e}", "error")
    return redirect(url_for("list_recordings"))

# Test route to confirm scheduled jobs can fire
@app.route("/trigger-test")
def trigger_test():
    print("Trigger test hit. Scheduling 5s job.")
    scheduler.add_job(lambda: print("🔥 Test job fired!"), trigger='date', run_date=datetime.now(timezone.utc) + timedelta(seconds=5))
    return "Scheduled test job."

@app.route("/test-schedule")
def test_schedule():
    now = datetime.now(timezone.utc) + timedelta(seconds=10)
    job_id = f"test_job_{now.timestamp()}"
    scheduler.add_job(lambda: print("🔥 Test job fired from /test-schedule"), trigger="date", run_date=now, id=job_id)
    print(f"[DEBUG] Test job added: {job_id}")
    return "Test job scheduled."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
