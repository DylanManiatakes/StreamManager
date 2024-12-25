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
    
 # Alsaaudio
@app.route("/alsa/volume", methods=["GET", "POST"])
def alsa_volume():
    mixer = alsaaudio.Mixer()
    if request.method == "POST":
        volume = int(request.form.get("volume"))
        mixer.setvolume(volume)
        return jsonify({"status": "success", "message": f"Volume set to {volume}"})
    else:
        current_volume = mixer.getvolume()[0]
        return render_template("alsa_volume.html", volume=current_volume)
    
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
