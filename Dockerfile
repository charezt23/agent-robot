FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8123

CMD ["langgraph", "dev", "--host", "0.0.0.0", "--port", "8123"]


