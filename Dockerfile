FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir flask gunicorn

COPY . .

EXPOSE 5000

CMD ["gunicorn", "web_app:app", "--bind", "0.0.0.0:5000", "--timeout", "120", "--workers", "2"]
