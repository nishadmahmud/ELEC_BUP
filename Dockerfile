FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json ./BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json
COPY scripts ./scripts

ENV PORT=8000
ENV OPENAI_MODEL=gpt-4o-mini
EXPOSE 8000

# Bind 0.0.0.0 for judge / container networking. No secrets baked in.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
