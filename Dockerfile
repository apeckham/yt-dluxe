# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Copy the setup file and app directory
COPY setup.py .
COPY yt_dluxe/ ./yt_dluxe/

# Install the package using setup.py
RUN pip install --upgrade pip && \
    pip install .

# Expose port 8000 (adjust if needed)
EXPOSE 5050

# Command to run the application
CMD ["python", "yt_dluxe/app.py"]
