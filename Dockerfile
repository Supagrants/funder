# Use Playwright base image with Ubuntu 22.04.4 LTS (v1.49.0)
FROM mcr.microsoft.com/playwright:v1.49.0-jammy

# Set the working directory
WORKDIR /app

# Install Python, pip, and PDF processing dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    libpq-dev \
    build-essential \
    poppler-utils \ 
    tesseract-ocr \ 
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file first to leverage Docker's caching mechanism
COPY requirements.txt /app/

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and its browser binaries (for crawling)
RUN pip install playwright
RUN playwright install

# Copy the rest of the application code
COPY src /app/

# Expose the port (if necessary)
EXPOSE 8080

# Command to run the FastAPI app using Uvicorn with multiple workers
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--reload", "--workers", "1"]