FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends nginx \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Required for session_api.py (add to requirements.txt): fastapi, uvicorn
RUN pip install --no-cache-dir 'fastapi>=0.115,<1' 'uvicorn>=0.30,<1'
COPY . .
COPY nginx.conf.template /etc/nginx/conf.d/default.conf
EXPOSE 10000
CMD sh -c 'uvicorn session_api:app --host 127.0.0.1 --port 8502 & streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true & nginx -g "daemon off;"'
