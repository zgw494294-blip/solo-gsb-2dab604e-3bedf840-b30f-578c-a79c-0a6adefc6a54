FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py optimizer.py allocate.py schedule.py batches.py quality.py joint.py dispatches.py ./
COPY static ./static

EXPOSE 8000

CMD ["python", "app.py"]
