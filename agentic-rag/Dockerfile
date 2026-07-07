FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/root/.cache/huggingface \
    TRANSFORMERS_CACHE=/root/.cache/huggingface \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Cài Python 3.10 + system deps
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3.10 \
        python3.10-dev \
        python3-pip \
        build-essential \
        libgomp1 \
    && ln -sf /usr/bin/python3.10 /usr/bin/python \
    && rm -rf /var/lib/apt/lists/*

# Cài PyTorch 2.7.0+cu118
RUN pip install --upgrade pip \
    && pip install torch==2.7.0 --index-url https://download.pytorch.org/whl/cu118

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY run.py ./run.py
COPY src ./src

RUN mkdir -p /app/logs_agent

EXPOSE 8081

CMD ["python", "run.py"]
