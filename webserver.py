from flask import Flask, request, jsonify, render_template, redirect, url_for, send_file, flash
import subprocess
import os
import alsaaudio
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta, timezone

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "streammanager-default-key")
DARKICE_CONFIG_PATH = "/etc/darkice/darkice.cfg"
RECORDINGS_DIR = "/opt/StreamManager/recordings"
os.makedirs(RECORDINGS_DIR, exist_ok=True)

scheduler = BackgroundScheduler()
scheduler.start()

# Dashboard route
@app.route("/")
def dashboard():
    darkice_status = check_service_status("darkice")
    jobs = scheduler.get_jobs()
    now = datetime.now()

    upcoming = None
    active_recording = is_recording_active()

    for job in jobs:
        if "recording_" in job.id:
            if job.next_run_time and job.next_run_time > now:
                upcoming = job.next_run_time

    return render_template(
        "index.html",
        darkice_status=darkice_status,
        upcoming_recording=upcoming,
        recording_active=active_recording,
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
    try:
        # Use ffmpeg to record from ALSA input device (hw:1,0 assumed)
        subprocess.run([
            "ffmpeg",
            "-f", "alsa",
            "-i", "shared_input",
            "-t", str(duration_seconds),
            "-acodec", "pcm_s16le",
            "-ar", "44100",
            filepath
        ], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Recording failed: {e}")

# Schedule a recording
@app.route("/recordings/schedule", methods=["POST"])
def schedule_recording():
    data = request.get_json()
    start_time_str = data.get("start_time")
    end_time_str = data.get("end_time")
    filename = data.get("filename")
    recurrence = data.get("recurrence", "once")

    if not start_time_str or not end_time_str or not filename:
        flash("Missing required fields", "error")
        return redirect(url_for("new_recording_form"))

    try:
        start_time = datetime.fromisoformat(start_time_str)
        end_time = datetime.fromisoformat(end_time_str)
        duration = (end_time - start_time).total_seconds()
        if duration <= 0:
            flash("End time must be after start time", "error")
            return redirect(url_for("new_recording_form"))

        def job_wrapper():
            run_time = datetime.now().strftime("%Y%m%d_%H%M")
            dated_filename = f"{filename.rstrip('.wav')}_{run_time}.wav"
            record_audio(dated_filename, duration)

        job_id = f"recording_{filename}_{start_time.timestamp()}"

        if recurrence == "once":
            scheduler.add_job(job_wrapper, trigger="date", run_date=start_time, id=job_id, kwargs={"start": start_time, "end": end_time})
        elif recurrence == "monday":
            scheduler.add_job(job_wrapper, trigger=CronTrigger(day_of_week="mon", hour=start_time.hour, minute=start_time.minute), id=job_id, replace_existing=True, kwargs={"start": start_time, "end": end_time})
        elif recurrence == "thursday":
            scheduler.add_job(job_wrapper, trigger=CronTrigger(day_of_week="thu", hour=start_time.hour, minute=start_time.minute), id=job_id, replace_existing=True, kwargs={"start": start_time, "end": end_time})
        else:
            flash("Invalid recurrence option", "error")
            return redirect(url_for("new_recording_form"))

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
    return render_template("new_recording.html")

def is_recording_active():
    now = datetime.now(timezone.utc)
    for job in scheduler.get_jobs():
        if "recording_" in job.id:
            # Parse start and end from job kwargs if available
            start = job.kwargs.get("start")
            end = job.kwargs.get("end")
            if start and end and start <= now <= end:
                return True
    return False

@app.route("/recordings/delete/<filename>", methods=["POST"])
def delete_recording(filename):
    path = os.path.join(RECORDINGS_DIR, filename)
    try:
        os.remove(path)
        flash(f"Deleted {filename}", "success")
    except Exception as e:
        flash(f"Failed to delete {filename}: {e}", "error")
    return redirect(url_for("list_recordings"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)