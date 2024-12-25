#!/bin/bash

echo "Starting Stream Full Installer..."

# Update system and install dependencies
echo "Updating system and installing dependencies..."
sudo apt update && sudo apt upgrade -y
sudo apt install -y darkice ffmpeg python3 python3-pip python3-venv libasound2-dev alsa-base || {
    echo "Failed to install required packages" >&2
    exit 1
}

# Set up Python environment
echo "Setting up Python environment..."
INSTALL_DIR="/opt/StreamManager"
mkdir -p "$INSTALL_DIR"
python3 -m venv "$INSTALL_DIR/env"
source "$INSTALL_DIR/env/bin/activate"
pip install flask pyalsaaudio || {
    echo "Failed to install Python dependencies" >&2
    exit 1
}

# Copy application files
echo "Copying application files..."
mkdir -p "$INSTALL_DIR/templates" "$INSTALL_DIR/static" "$INSTALL_DIR/scripts"
cp ./webserver.py "$INSTALL_DIR/webserver.py"
cp -r ./templates/* "$INSTALL_DIR/templates/"
cp -r ./static/* "$INSTALL_DIR/static/"
cp -r ./scripts/* "$INSTALL_DIR/scripts/"
chmod +x "$INSTALL_DIR/scripts/watchdog.sh"

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

# Install systemd service for StreamManager
echo "Installing systemd service for StreamManager..."
cat <<EOF > /etc/systemd/system/StreamManager.service
[Unit]
Description=Stream Manager
After=network.target sound.target

[Service]
ExecStartPre=/bin/bash -c 'pgrep darkice || sudo systemctl start darkice'
ExecStartPre=/bin/bash -c 'pgrep ffmpeg || echo "Starting FFmpeg if configured separately."'
ExecStart=/bin/bash -c 'source $INSTALL_DIR/env/bin/activate && python3 $INSTALL_DIR/webserver.py'
WorkingDirectory=$INSTALL_DIR
User=root
Group=root
Restart=always
RestartSec=5
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
EOF

# Install systemd service for DarkIce
echo "Installing systemd service for DarkIce..."
cat <<EOF > /etc/systemd/system/darkice.service
[Unit]
Description=DarkIce Streaming Service
After=network.target StreamManager.service
BindsTo=StreamManager.service
PartOf=StreamManager.service

[Service]
ExecStart=/usr/bin/darkice -c /etc/darkice/darkice.cfg
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Install systemd service for FFmpeg
echo "Installing systemd service for FFmpeg..."
cat <<EOF > /etc/systemd/system/ffmpeg-stream.service
[Unit]
Description=FFmpeg Stream Service
After=network.target sound.target StreamManager.service
BindsTo=StreamManager.service
PartOf=StreamManager.service

[Service]
ExecStart=/usr/bin/ffmpeg -f alsa -i hw:0,0 -c:a libmp3lame -b:a 64k -f mp3 icecast://source:password@localhost:8000/stream
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Reload and enable services
echo "Reloading and enabling systemd services..."
sudo systemctl daemon-reload
sudo systemctl enable StreamManager.service
sudo systemctl enable darkice.service
sudo systemctl enable ffmpeg-stream.service
sudo systemctl start StreamManager.service

echo "Stream Manager and dependent services installed and started!"