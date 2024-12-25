# Use Ubuntu 24.04 as the base image
FROM ubuntu:24.04

# Set environment variables to prevent prompts during installation
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Set the working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-venv \
    darkice ffmpeg alsa-utils libasound2-dev systemd \
    && rm -rf /var/lib/apt/lists/*

# Copy application files
COPY . /app/

# Set up Python dependencies
RUN python3 -m venv /app/env && \
    /app/env/bin/pip install --no-cache-dir flask pyalsaaudio

# Expose the Flask app port
EXPOSE 8080

# Copy service files to systemd directory
RUN mkdir -p /etc/systemd/system/ && \
    cp /app/services/*.service /etc/systemd/system/

# Enable and start necessary services
RUN systemctl enable darkice.service ffmpeg-stream.service StreamManager.service

# Start the Flask application
CMD ["/bin/bash", "-c", "source /app/env/bin/activate && python /app/webserver.py"]