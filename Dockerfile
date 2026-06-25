FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y nginx \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

COPY nginx.conf.template /etc/nginx/conf.d/default.conf

EXPOSE 10000

CMD sh -c 'streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true & nginx -g "daemon off;"'
