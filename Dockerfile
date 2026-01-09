# DistrictWatch Docker Image
FROM python:3.11-slim

# Install Playwright dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libasound2 libpango-1.0-0 libcairo2 \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser
RUN playwright install chromium

# Copy application
COPY *.py ./

# Create data directories
RUN mkdir -p data logs

# Run as non-root
RUN useradd -m -u 1000 watcher && chown -R watcher:watcher /app
USER watcher

# Health check
HEALTHCHECK --interval=5m --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "from state import StateManager; s=StateManager('data/state.db'); s.initialize(); exit(0 if s.get_check_count() >= 0 else 1)"

CMD ["python", "-u", "main.py"]
