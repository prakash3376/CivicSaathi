# CivicSaathi as one container: the API serves the built website on the same origin.
# Built by Hugging Face Spaces from the folder `stage.py` prepares (see README.md here).
# Settings (GEMINI_API_KEY, ADMIN_TOKEN, ...) are never in the image: they are Space secrets.

FROM node:22-slim AS website
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Spaces run the container as user 1000.
RUN useradd -m -u 1000 user
USER user
ENV PATH=/home/user/.local/bin:$PATH \
    APP_ENV=production \
    LOG_LEVEL=INFO \
    FRONTEND_DIR=/home/user/app/frontend/dist \
    DATA_DIR=/home/user/app/backend/storage

WORKDIR /home/user/app/backend
COPY --chown=user backend/requirements.txt backend/constraints.txt ./
RUN pip install --user -r requirements.txt -c constraints.txt

COPY --chown=user backend/pyproject.toml ./
COPY --chown=user backend/app ./app
COPY --chown=user backend/data ./data
COPY --chown=user --from=website /web/dist /home/user/app/frontend/dist

# The document index was built with `ingest` on the developer's machine. The embedding model is
# downloaded here (fast inside Hugging Face). `search` exits with an error if the index is empty or
# unreadable, which fails the build instead of shipping a site that answers nothing.
COPY --chown=user backend/storage/chroma ./storage/chroma
RUN python -m app.cli search "maximum family income scholarship" | head -5

EXPOSE 7860
# --proxy-headers: the visitor's address comes from the proxy, so the per-client rate limit counts
# each visitor, not the proxy. The container is reachable only through that proxy.
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
