#!/bin/bash

# Check and restart DarkIce
if ! pgrep -x "darkice" > /dev/null; then
    echo "$(date) - DarkIce is not running. Restarting..." >> /var/log/streammanager.log
    sudo systemctl restart darkice
else
    echo "$(date) - DarkIce is running." >> /var/log/streammanager.log
fi

# Check and restart FFmpeg
if ! pgrep -x "ffmpeg" > /dev/null; then
    echo "$(date) - FFmpeg is not running. Restarting..." >> /var/log/streammanager.log
    # Example FFmpeg command - replace with actual streaming command
    ffmpeg -f alsa -i default -c:a libmp3lame -b:a 64k -f mp3 icecast://user:password@server:port/mountpoint &
else
    echo "$(date) - FFmpeg is running." >> /var/log/streammanager.log
fi