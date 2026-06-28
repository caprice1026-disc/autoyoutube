FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    AIVIS_SPEECH_BASE_URL=http://aivis-engine:10101 \
    FFMPEG_PATH=/usr/bin/ffmpeg

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT ["python", "-m", "src.main"]
CMD ["--help"]
