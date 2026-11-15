FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir zigpy colorama paho-mqtt pyserial

COPY src/ /app/src/

CMD ["python3", "src/simulation_daemon.py"]
