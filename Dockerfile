# syntax=docker/dockerfile:1

# Use the official Python base image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Updates and default installs
RUN apt update && apt-get update && pip install --upgrade pip && apt-get install -y git

# Copy the requirements file and .env file to the container
COPY requirements.txt .

# Install the required libraries
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

# Setup python path
ENV PYTHONUNBUFFERED 1
ENV PYTHONPATH=/app

# Set the entry point for the container
CMD ["python3", "main.py"]
