FROM python:3.12-slim

# Add non-root user
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 -ms /bin/bash appuser

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Switch to non-root user
USER appuser
WORKDIR /home/appuser

# Install Python dependencies first (for caching)
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Copy the rest of the app
COPY --chown=appuser:appuser . .

# Set entrypoint
COPY --chown=appuser:appuser run.sh .
RUN chmod +x run.sh
EXPOSE 8501
ENTRYPOINT ["./run.sh"]