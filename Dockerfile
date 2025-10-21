# Use an official Python runtime as a parent image.
# Using a specific version like 3.9-slim-buster is good for reproducibility.
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required by rasterio (GDAL).
# Using --no-install-recommends keeps the image size down.
RUN apt-get update && \
    apt-get install -y --no-install-recommends libgdal-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy the requirements file first to leverage Docker layer caching.
# This layer is only rebuilt if requirements.txt changes.
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code into the container
COPY fm40_updater .
COPY data ../data

# Open bash terminal so we can run main.py ourselves with cli args
CMD ["bash"]