# Dockerfile
# --- Instructions to build a secure, multi-stage container ---

# --- Stage 1: The Builder ---
FROM python:3.12-slim as builder

# Set the working directory
WORKDIR /app

# Install OS-level build dependencies that might be needed
RUN apt-get update && apt-get install -y --no-install-recommends gcc build-essential && rm -rf /var/lib/apt/lists/*

# Upgrade core packaging tools first
RUN pip install --no-cache-dir --upgrade pip setuptools

# Copy only the requirements file to leverage Docker cache
COPY requirements.txt .
# Install the Python dependencies
# Using --upgrade-strategy eager ensures that dependencies are upgraded
RUN pip install --no-cache-dir --upgrade-strategy eager -r requirements.txt


# --- Stage 2: The Final Image ---
FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# Apply OS-level security patches to the final image
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN addgroup --system app && adduser --system --group app

# --- Copy installed packages AND executables from the builder stage ---
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy the rest of the application code
COPY app.py .
COPY logging_config.py .
COPY special_files/ ./special_files/

# Change the owner of the /app directory to our new user
RUN chown -R app:app /app

# Switch to the non-root user
USER app

# Make port 8080 available
EXPOSE 8080

# Run Gunicorn with a configurable number of workers
CMD exec gunicorn --worker-class gevent --workers ${GUNICORN_WORKERS:-3} --bind 0.0.0.0:8080 "app:app"