from flask import Flask, request, jsonify, render_template, redirect, url_for
import subprocess
import os
import alsaaudio

app = Flask(__name__)
DARKICE_CONFIG_PATH = "/etc/darkice/darkice.cfg"

# Dashboard route
@app.route("/")
def dashboard():
    darkice_status = check_service_status("darkice")
    ffmpeg_status = check_service_status("ffmpeg-stream")
    icecast_status = check_service_status("icecast2")  # Correct service name for Icecast
    return render_template(
        "index.html",
        darkice_status=darkice_status,
        ffmpeg_status=ffmpeg_status,
        icecast_status=icecast_status,
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

# Restart FFmpeg
@app.route("/ffmpeg/restart", methods=["POST"])
def restart_ffmpeg_service():
    try:
        subprocess.run(["sudo", "systemctl", "restart", "ffmpeg-stream.service"], check=True)
        return jsonify({"status": "success", "message": "FFmpeg restarted successfully"})
    except subprocess.CalledProcessError as e:
        return jsonify({"status": "error", "message": f"Failed to restart FFmpeg: {str(e)}"})

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
    mixer = alsaaudio.Mixer()  # Initialize mixer for volume control

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

            # Restart DarkIce/FFmpeg to apply changes
            subprocess.run(["sudo", "systemctl", "restart", "darkice"], check=True)
            subprocess.run(["sudo", "systemctl", "restart", "ffmpeg-stream.service"], check=True)
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

# Check Icecast status
@app.route("/icecast/status", methods=["GET"])
def check_icecast_status():
    status = check_service_status("icecast2")
    return jsonify({"status": status})

# Open Icecast Server in Browser
@app.route("/icecast/open", methods=["GET"])
def open_icecast():
    return jsonify({"url": "http://localhost:8000"})

# Restart Icecast service
@app.route("/icecast/restart", methods=["POST"])
def restart_icecast():
    try:
        subprocess.run(["sudo", "systemctl", "restart", "icecast2"], check=True)
        return jsonify({"status": "success", "message": "Icecast restarted successfully"})
    except subprocess.CalledProcessError as e:
        return jsonify({"status": "error", "message": f"Failed to restart Icecast: {str(e)}"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)