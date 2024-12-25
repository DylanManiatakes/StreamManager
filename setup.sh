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
cp ./templates/index.html "$INSTALL_DIR/templates/index.html"
cp ./templates/edit_darkice.html "$INSTALL_DIR/templates/edit_darkice.html"
cp -r ./static/* "$INSTALL_DIR/static/"
cp ./scripts/watchdog.sh "$INSTALL_DIR/scripts/watchdog.sh"
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

# Install systemd service
echo "Installing systemd service with virtual environment support..."
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

sudo systemctl daemon-reload
sudo systemctl enable StreamManager.service
sudo systemctl start StreamManager.service

echo "Stream Manager Service with DarkIce and FFmpeg control installed and started!"
