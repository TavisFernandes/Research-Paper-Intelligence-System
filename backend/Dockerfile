FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt requirements-ml.txt ./
# Core install. To bake in the ML stack (BGE-M3, LED, OCR) build with: --build-arg INSTALL_ML=1
ARG INSTALL_ML=0
RUN pip install --no-cache-dir -r requirements.txt \
 && python -m spacy download en_core_web_sm \
 && if [ "$INSTALL_ML" = "1" ]; then pip install --no-cache-dir -r requirements-ml.txt; fi
COPY . .
RUN useradd -m app && mkdir -p /app/data && chown -R app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
