# Telos — container image for ECS Fargate behind an Application Load Balancer.
#
# Note on hosting: Streamlit communicates with the browser over a WebSocket.
# AWS App Runner does not support WebSockets, so this image will appear to
# start correctly there and then hang on a loading spinner forever. It must
# run behind something that proxies WebSockets — an ALB does.

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Build deps for psycopg2 / pdfplumber / pillow, removed after the wheel build.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY app.py ./
COPY core/ ./core/
COPY pages/ ./pages/
COPY .streamlit/ ./.streamlit/

# Run unprivileged.
RUN useradd --create-home --shell /bin/bash telos && chown -R telos:telos /app
USER telos

EXPOSE 8501

# ALB target-group health checks hit this path.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
