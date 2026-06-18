# Use official Python runtime as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Cloud Run sets PORT env var, default to 8080
ENV PORT=8080

# Run FastAPI with uvicorn
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT}
