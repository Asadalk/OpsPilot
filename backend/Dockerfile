FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt ./
RUN pip install --upgrade pip \
	&& pip install --no-cache-dir --retries 10 --timeout 120 -r requirements.txt

COPY . .

# Run as an unprivileged user; the app only reads its code and the mounted knowledge.
RUN useradd --create-home --uid 10001 opspilot
USER opspilot

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
