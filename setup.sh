#!/bin/bash

echo "Starting Stream Full Installer..."

# Update system and install dependencies
echo "Updating system and installing dependencies..."
sudo apt update && sudo apt upgrade -y
sudo apt install -y darkice ffmpeg python3 python3-pip python3-venv || {
    echo "Failed to install required packages" >&2
    exit 1
}

# Set up Python environment
echo "Setting up Python environment..."
mkdir -p /opt/StreamManager
python3 -m venv /opt/StreamManager/env
source /opt/StreamManager/env/bin/activate
pip install flask || {
    echo "Failed to install Flask" >&2
    exit 1
}

# Copy application files
echo "Copying application files..."
mkdir -p /opt/StreamManager/templates
mkdir -p /opt/StreamManager/static
mkdir -p /opt/StreamManager/scripts

cp ./webserver.py /opt/StreamManager/webserver.py
cp ./templates/index.html /opt/StreamManager/templates/index.html
cp ./templates/edit_darkice.html /opt/StreamManager/templates/edit_darkice.html
cp -r ./static/* /opt/StreamManager/static/
cp ./scripts/watchdog.sh /opt/StreamManager/scripts/watchdog.sh

# Make watchdog script executable
chmod +x /opt/StreamManager/scripts/watchdog.sh

cp ./webserver.py /opt/StreamManager/webserver.py
cp ./templates/index.html /opt/StreamManager/templates/index.html
cp ./scripts/watchdog.sh /opt/StreamManager/scripts/watchdog.sh

# Make watchdog script executable
chmod +x /opt/StreamManager/scripts/watchdog.sh

# Create DarkIce configuration
echo "Creating default DarkIce configuration..."
mkdir -p /etc/darkice
cat <<EOF > /etc/darkice/darkice.cfg
[general]
duration        = 0
bufferSecs      = 5
reconnect       = yes

[input]
device          = default
sampleRate      = 44100
bitsPerSample   = 16
channel         = 1

[icecast2-0]
bitrateMode     = cbr
format          = mp3
bitrate         = 64
server          = icecast.broadcastify.com
port            = 8000
password        = YOUR_PASSWORD
mountPoint      = YOUR_MOUNTPOINT
EOF

# Install systemd service
echo "Installing systemd service with virtual environment support..."
cat <<EOF > /etc/systemd/system/StreamManager.service
[Unit]
Description=Stream Manager
After=network.target sound.target

[Service]
ExecStartPre=/bin/bash -c 'pgrep darkice || sudo systemctl start darkice'
ExecStartPre=/bin/bash -c 'pgrep ffmpeg || echo "Starting FFmpeg if configured separately."'
ExecStart=/bin/bash -c 'source /opt/StreamManager/env/bin/activate && python3 /opt/StreamManager/webserver.py'
WorkingDirectory=/opt/StreamManager
User=root
Group=root
Restart=always
RestartSec=5
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable StreamManager.service
sudo systemctl start StreamManager.service

echo "Stream Manager Service with DarkIce and FFmpeg control installed and started!"