# Tanaw hosted demo (Hugging Face Spaces, Docker SDK). Builds everything from the public GitHub repository.
# Upload this file and deploy/huggingface/README.md to the root of the Space; nothing else is needed.

# ---- 1. frontend: static export (the full node image already includes git) ------------------------
FROM node:20 AS web
ARG TANAW_REPO=https://github.com/Jonnywik/NASA-SA-Final.git
ARG TANAW_REF=main
RUN git clone --depth 1 --branch "$TANAW_REF" "$TANAW_REPO" /src
WORKDIR /src/frontend
RUN npm ci --no-audit --no-fund \
 && (TANAW_STATIC_EXPORT=1 NEXT_PUBLIC_API_URL=same-origin npm run build \
     || TANAW_STATIC_EXPORT=1 NEXT_PUBLIC_API_URL=same-origin npm run build)  # retry once: next/font downloads Google Fonts

# ---- 2. backend + data + static files -----------------------------------------------------------
# Full image (not -slim): the rasterio wheels need system libraries such as libexpat.
FROM python:3.12
ENV PYTHONUNBUFFERED=1 PORT=7860
WORKDIR /app
COPY --from=web /src/backend ./backend
COPY --from=web /src/deploy ./deploy
COPY --from=web /src/frontend/out ./frontend/out
RUN pip install --no-cache-dir -r backend/requirements.txt
# The processed NISAR product (tanaw-data-camanava_2026-v1) from the data-package-v1 branch, checksum-verified.
RUN python deploy/fetch_data.py --dest /app

# Spaces run the container as user 1000.
RUN useradd -m -u 1000 tanaw && chown -R tanaw /app
USER tanaw
EXPOSE 7860
CMD ["python", "deploy/serve.py"]
