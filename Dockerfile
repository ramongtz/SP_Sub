# Dockerfile
# --- Instructions to build the container ---

# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Create a non-root user
RUN addgroup --system app && adduser --system --group app

# Copy the requirements file into the container at /app
COPY requirements.txt .
# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY app.py .
# --- FIX: Add this line to copy the new logging configuration ---
COPY logging_config.py .

# Copy the special KnowBe4 file into the container
COPY special_files/ ./special_files/

# Change the owner of the /app directory to our new user
RUN chown -R app:app /app

# Switch to the non-root user
USER app

# Make port 8080 available to the world outside this container
EXPOSE 8080

# Run the app with Gunicorn and a gevent worker for better streaming
CMD ["gunicorn", "--worker-class", "gevent", "--bind", "0.0.0.0:8080", "app:app"]