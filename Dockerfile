FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

# Run as non-root for security (D-08)
RUN addgroup --system botuser && adduser --system --ingroup botuser botuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ bot/

USER botuser

CMD ["python", "-m", "bot"]
