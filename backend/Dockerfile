# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set environment variables to prevent Python from writing .pyc files
# and to ensure output is sent straight to the terminal without buffering.
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies that might be needed (e.g., for Pillow or psycopg2)
# RUN apt-get update && apt-get install -y --no-install-recommends some-package && rm -rf /var/lib/apt/lists/*
# Add specific dependencies if Pillow or psycopg2 require them on slim image

# Install Python dependencies
# Copy only requirements.txt first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project code into the working directory
COPY . .

# Expose the port Gunicorn will run on
EXPOSE 8000

# Command to run the application using Gunicorn
# Use a non-root user for better security. Gunicorn creates 'nobody' user.
# Adjust the number of workers based on your server's resources.
# The module path 'backend.wsgi:application' should match your project structure.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "backend.wsgi:application", "--workers", "4", "--user", "nobody", "--group", "nogroup"]

# Optional: Add an entrypoint script for running migrations, etc.
# COPY entrypoint.sh /app/entrypoint.sh
# RUN chmod +x /app/entrypoint.sh
# ENTRYPOINT ["/app/entrypoint.sh"]