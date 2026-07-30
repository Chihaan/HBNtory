FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV MCP_TRANSPORT=http
ENV MCP_PORT=8001

EXPOSE 8001

CMD ["python", "server.py"]
