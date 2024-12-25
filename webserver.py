from flask import Flask, request, jsonify, render_template, redirect, url_for
import subprocess
import os

app = Flask(__name__)
DARKICE_CONFIG_PATH = "/etc/darkice/darkice.cfg"

# Dashboard route
@app.route("/")
def dashboard():
    darkice_status = check_service_status("darkice")
    ffmpeg_status = check_service_status("ffmpeg")
    return render_template("index.html", darkice_status=darkice_status, ffmpeg_status=ffmpeg_status)

# Helper function to check service status
def check_service_status(service_name):
    try:
        result = subprocess.run(["systemctl", "is-active", service_name], capture_output=True, text=True)
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
def restart_ffmpeg():
    try:
        subprocess.run(["sudo", "pkill", "-f", "ffmpeg"])
        subprocess.Popen(["ffmpeg", "-f", "alsa", "-i", "default", "-c:a", "libmp3lame", "-b:a", "64k",
                          "-f", "mp3", "icecast://user:password@server:port/mountpoint"])
        return jsonify({"status": "success", "message": "FFmpeg restarted successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to restart FFmpeg: {e}"})

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