
# StreamManager

**StreamManager** is a Python-based application for managing audio streams using DarkIce, FFmpeg, and ALSA. It provides a web-based interface for controlling audio services and configurations, including real-time updates and editable configurations.

---

## Features
- **Web-based Management**: Control and monitor DarkIce, FFmpeg, and ALSA through a clean and responsive web interface.
- **DarkIce Configuration**: Edit `darkice.cfg` directly from the web UI.
- **ALSA Mixer Integration**: Manage audio settings like volume and input sources.
- **FFmpeg Service**: Start and monitor FFmpeg streams as a systemd service.

---

## Installation

### Prerequisites
Ensure you have the following installed on your system:
- **Linux (Debian/Ubuntu)**.
- Python 3.8+.
- System dependencies: `darkice`, `ffmpeg`, `alsa-base`, `libasound2-dev`.

### Quick Start
1. Clone the repository:
   ```bash
   git clone https://github.com/DylanManiatakes/StreamManager.git
   cd StreamManager
   sudo chmod +x setup.sh
   sudo ./setup.sh
   ```

2. Access the web interface:
   Open your browser and navigate to:
   ```
   http://<server-ip>:5000
   ```

---

## Configuration

### DarkIce
Edit the `darkice.cfg` file:
```bash
sudo nano /etc/darkice/darkice.cfg
```
You can also edit this configuration via the web interface.

### FFmpeg
FFmpeg is configured as a systemd service. Modify its behavior by editing `/etc/systemd/system/ffmpeg-stream.service`.

---

## Development

### Run Locally
Activate the virtual environment:
```bash
source /opt/StreamManager/env/bin/activate
```

Run the web server:
```bash
python3 /opt/StreamManager/webserver.py
```

---

## Contributing
Feel free to contribute by submitting issues or pull requests to the repository.

---

## License
This project is licensed under the MIT License.
