FROM python:3.11-slim

WORKDIR /app

# Tini forwards shutdown signals and reaps orphaned processes.
RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx tini bash \
    && rm -rf /var/lib/apt/lists/*

# Use the versions actually observed in the working staging container.
COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt \
    && python -m pip check

COPY . .
COPY nginx.conf.template /etc/nginx/conf.d/default.conf

EXPOSE 10000

# If any of FastAPI, Streamlit, or Nginx stops, terminate all three.
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["bash", "-c", "set -Eeuo pipefail;\nuvicorn session_api:app --host 127.0.0.1 --port 8502 & api=$!;\nstreamlit run app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true & ui=$!;\nnginx -g 'daemon off;' & proxy=$!;\ntrap 'kill -TERM \"$api\" \"$ui\" \"$proxy\" 2>/dev/null || true; wait 2>/dev/null || true' EXIT;\ntrap 'exit 143' TERM;\ntrap 'exit 130' INT;\nwait -n \"$api\" \"$ui\" \"$proxy\" || true;\necho 'A critical service stopped. Exiting so the host can restart the container.' >&2;\nexit 1"]
