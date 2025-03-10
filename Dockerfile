# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app
RUN chmod 777 /app

# Install ffmpeg from yt-dlp builds based on architecture
RUN apt-get update && \
    apt-get install -y wget xz-utils && \
    if [ "$(uname -m)" = "aarch64" ]; then \
        wget https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linuxarm64-gpl.tar.xz && \
        tar xf ffmpeg-master-latest-linuxarm64-gpl.tar.xz && \
        cp ffmpeg-master-latest-linuxarm64-gpl/bin/* /usr/local/bin/ && \
        rm -rf ffmpeg-master-latest-linuxarm64-gpl*; \
    else \
        wget https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz && \
        tar xf ffmpeg-master-latest-linux64-gpl.tar.xz && \
        cp ffmpeg-master-latest-linux64-gpl/bin/* /usr/local/bin/ && \
        rm -rf ffmpeg-master-latest-linux64-gpl*; \
    fi && \
    apt-get remove -y wget xz-utils && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# Copy the setup file and app directory
COPY setup.py .
COPY yt_dluxe/ ./yt_dluxe/

# Install the package using setup.py
RUN pip install --upgrade pip && \
    pip install .

# Expose port 8000 (adjust if needed)
EXPOSE 5051

# Set the entrypoint to allow passing arguments
ENTRYPOINT ["python", "yt_dluxe/app.py"]
