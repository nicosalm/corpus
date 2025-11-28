# Use Python 3.11 slim image
FROM python:3.11-slim

# Copy uv from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files and app code
COPY pyproject.toml ./
COPY app ./app

# Install dependencies (cached layer)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -e .

# Copy remaining files (tests, scripts, etc)
COPY . .

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
