FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --system --uid 10001 shopbot \
    && install -d -o shopbot -g shopbot -m 0700 /data
COPY main.py database.py price_list.py stars.py price-list.example.json ./

USER shopbot
CMD ["python", "main.py"]
