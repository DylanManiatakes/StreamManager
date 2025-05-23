#!/bin/bash

echo "Starting StreamManager installer..."

INSTALL_DIR="/opt/StreamManager"
REPO_URL="https://github.com/DylanManiatakes/StreamManager.git"

# Install dependencies
echo "Installing dependencies..."
sudo apt update && sudo apt install -y darkice ffmpeg python3 python3-pip python3-venv libasound2-dev alsa-base git || {
    echo "Dependency installation failed" >&2
    exit 1
}

# Preserve DarkIce config if it exists
if [ -f /etc/darkice/darkice.cfg ]; then
    echo "Preserving existing DarkIce config"
    sudo cp /etc/darkice/darkice.cfg /tmp/darkice.cfg.bak
fi

# Clone or update the StreamManager repo
if [ ! -d "$INSTALL_DIR/.git" ]; then
    echo "Cloning repository..."
    sudo git clone "$REPO_URL" "$INSTALL_DIR"
else
    echo "Updating existing repository..."
    cd "$INSTALL_DIR" || exit
    sudo git pull
fi

# Restore DarkIce config if backed up
if [ -f /tmp/darkice.cfg.bak ]; then
    echo "Restoring preserved DarkIce config"
    sudo cp /tmp/darkice.cfg.bak /etc/darkice/darkice.cfg
fi

# Set up Python virtual environment
echo "Setting up Python environment..."
python3 -m venv "$INSTALL_DIR/env"
source "$INSTALL_DIR/env/bin/activate"
pip install --upgrade pip
pip install flask pyalsaaudio apscheduler

# Copy templates and static files
echo "Copying application files..."
mkdir -p "$INSTALL_DIR/recordings"
sudo cp -r "$INSTALL_DIR/templates" "$INSTALL_DIR/static" "$INSTALL_DIR/scripts" /opt/StreamManager/

# Install systemd services
echo "Installing systemd services..."
sudo tee /etc/systemd/system/StreamManager.service > /dev/null <<EOF
[Unit]
Description=Stream Manager
After=network.target sound.target

[Service]
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

sudo tee /etc/systemd/system/darkice.service > /dev/null <<EOF
[Unit]
Description=DarkIce Streaming Service
After=network.target StreamManager.service

[Service]
ExecStart=/usr/bin/darkice -c /etc/darkice/darkice.cfg
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and start services
echo "Enabling and starting services..."
sudo systemctl daemon-reload
sudo systemctl enable StreamManager.service
sudo systemctl enable darkice.service
sudo systemctl restart StreamManager.service
sudo systemctl restart darkice.service

echo "StreamManager installation complete!"