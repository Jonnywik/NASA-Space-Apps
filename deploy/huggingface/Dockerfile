# Tanaw hosted demo (Hugging Face Spaces, Docker SDK). Builds everything from the public GitHub repository.
# Upload this file and deploy/huggingface/README.md to the root of the Space; nothing else is needed.

# ---- 1. frontend: static export ------------------------------------------------------------------
FROM node:20-slim AS web
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
ARG TANAW_REPO=https://github.com/Jonnywik/NASA-SA-Final.git
ARG TANAW_REF=main
RUN git clone --depth 1 --branch "$TANAW_REF" "$TANAW_REPO" /src
WORKDIR /src/frontend
RUN npm ci --no-audit --no-fund \
 && (TANAW_STATIC_EXPORT=1 NEXT_PUBLIC_API_URL=same-origin npm run build \
     || TANAW_STATIC_EXPORT=1 NEXT_PUBLIC_API_URL=same-origin npm run build)  # retry once: next/font downloads Google Fonts

# ---- 2. backend + data + static files -----------------------------------------------------------
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PORT=7860
RUN apt-get update && apt-get install -y --no-install-recommends curl unzip ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=web /src/backend ./backend
COPY --from=web /src/deploy ./deploy
COPY --from=web /src/frontend/out ./frontend/out
RUN pip install --no-cache-dir -r backend/requirements.txt

# The processed NISAR product (tanaw-data-camanava_2026-v1), from the repository's data-package-v1 branch.
ARG DATA_BASE=https://raw.githubusercontent.com/Jonnywik/NASA-SA-Final/data-package-v1
ARG DATA_SHA256=3290a66b2fc115bd666c1f199c17c7e5d0c6f978132264eb28335219110a2cfa
RUN for i in 00 01 02 03; do curl -fsSL "$DATA_BASE/tanaw-data-camanava_2026-v1.zip.part$i" >> /tmp/data.zip; done \
 && echo "$DATA_SHA256  /tmp/data.zip" | sha256sum -c - \
 && unzip -q /tmp/data.zip -d /app && rm /tmp/data.zip

# Spaces run the container as user 1000.
RUN useradd -m -u 1000 tanaw && chown -R tanaw /app
USER tanaw
EXPOSE 7860
CMD ["python", "deploy/serve.py"]
