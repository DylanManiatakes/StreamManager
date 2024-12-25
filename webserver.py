from flask import Flask, render_template, request, jsonify
import subprocess

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/darkice/restart", methods=["POST"])
def restart_darkice():
    try:
        subprocess.run(["sudo", "systemctl", "restart", "darkice"], check=True)
        return jsonify({"status": "success", "message": "DarkIce restarted successfully."})
    except subprocess.CalledProcessError:
        return jsonify({"status": "error", "message": "Failed to restart DarkIce."})

@app.route("/ffmpeg/start", methods=["POST"])
def start_ffmpeg():
    data = request.json
    # Placeholder for actual FFmpeg command
    return jsonify({"status": "success", "message": f"FFmpeg started with: {data}"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
