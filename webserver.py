from flask import Flask, request, jsonify, render_template, redirect, url_for
import subprocess
import os
import alsaaudio
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta

app = Flask(__name__)
DARKICE_CONFIG_PATH = "/etc/darkice/darkice.cfg"
RECORDINGS_DIR = "/opt/StreamManager/recordings"
os.makedirs(RECORDINGS_DIR, exist_ok=True)

scheduler = BackgroundScheduler()
scheduler.start()

# Dashboard route
@app.route("/")
def dashboard():
    darkice_status = check_service_status("darkice")
    return render_template(
        "index.html",
        darkice_status=darkice_status,
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
            with open(DARKICE_CONFIG_PATH, "w") as config_file:
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
    mixer = alsaaudio.Mixer(control='Capture', cardindex=1)  # Initialize mixer for input device volume control

    if request.method == "POST":
        # Handle device selection
        playback_device = request.form.get("playback_device")
        mic_device = request.form.get("mic_device")

        # Handle volume adjustment
        if "volume" in request.form:
            volume = int(request.form.get("volume"))
            mixer.setvolume(volume)

        try:
            # Save selected devices to a config file or apply immediately
            with open("/opt/StreamManager/alsa_devices.cfg", "w") as device_file:
                device_file.write(f"playback_device={playback_device}\n")
                device_file.write(f"mic_device={mic_device}\n")

            # Restart DarkIce to apply changes
            subprocess.run(["sudo", "systemctl", "restart", "darkice"], check=True)
            return redirect(url_for("manage_alsa"))
        except Exception as e:
            return f"Failed to update devices: {e}"

    else:
        # Retrieve available ALSA devices
        cards = alsaaudio.cards()
        mixers = alsaaudio.mixers()

        # Get current volume
        current_volume = mixer.getvolume()[0]

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
            "-i", "hw:1,0",
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

    if not start_time_str or not end_time_str or not filename:
        return jsonify({"status": "error", "message": "Missing required fields"})

    try:
        start_time = datetime.fromisoformat(start_time_str)
        end_time = datetime.fromisoformat(end_time_str)
        duration = (end_time - start_time).total_seconds()
        if duration <= 0:
            return jsonify({"status": "error", "message": "End time must be after start time"})

        # Schedule the recording job
        scheduler.add_job(
            func=record_audio,
            trigger='date',
            run_date=start_time,
            args=[filename, int(duration)],
            id=f"recording_{filename}_{start_time.timestamp()}",
            replace_existing=True
        )
        return jsonify({"status": "success", "message": "Recording scheduled successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to schedule recording: {str(e)}"})

# List recordings
@app.route("/recordings", methods=["GET"])
def list_recordings():
    try:
        files = os.listdir(RECORDINGS_DIR)
        recordings = [f for f in files if f.lower().endswith(".wav")]
        return jsonify({"recordings": recordings})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to list recordings: {str(e)}"})

# Serve form to schedule new recording
@app.route("/recordings/new", methods=["GET"])
def new_recording_form():
    return render_template("new_recording.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)