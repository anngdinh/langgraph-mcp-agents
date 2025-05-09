FROM python:3.12-slim

# Add app user
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 -ms /bin/bash appuser

# Install Python tools
RUN pip3 install --no-cache-dir --upgrade \
    pip \
    virtualenv

# Install system dependencies including Node.js and npx
RUN apt-get update && apt-get install -y \
    build-essential \
    software-properties-common \
    curl \
    git \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Switch to non-root user
USER appuser
WORKDIR /home/appuser

# Copy app code
COPY . .

# Setup virtual environment and install Python dependencies
ENV VIRTUAL_ENV=/home/appuser/venv
RUN virtualenv ${VIRTUAL_ENV}
RUN . ${VIRTUAL_ENV}/bin/activate && pip install -r requirements.txt

# Expose port for the app
EXPOSE 8501

# Copy and set entrypoint
COPY run.sh /home/appuser
ENTRYPOINT ["./run.sh"]
