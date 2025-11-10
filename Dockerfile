# Use Ubuntu 24.04 as base image (includes Python 3.12)
FROM ubuntu:24.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv
FROM python:3.12-slim-trixie
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY data/ ./data/
COPY hypercorn_config.toml ./

# Install Python dependencies using uv
RUN uv sync --frozen

# Expose port 8000
EXPOSE 8000

# Run the application
# CMD ["uv", "run", "hypercorn", "-c", "hypercorn_config.toml", "src.main:app"]
CMD ["/bin/bash"]
