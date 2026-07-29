FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENTRYPOINT ["sh", "./docker-entrypoint.sh"]
CMD ["python", "-m", "flask", "--app", "app:create_app", "run", "--debug", "--host=0.0.0.0", "--port=8000"]
