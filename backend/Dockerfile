FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/ai
WORKDIR /app
COPY server/requirements.txt server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt
COPY ai ai
RUN pip install --no-cache-dir -e ai
COPY server server
RUN useradd --uid 10001 --create-home buddy
USER buddy
EXPOSE 5050
CMD ["sh", "-c", "python -m server.store migrate && python -m server.store seed && exec python -m waitress --listen=0.0.0.0:5050 --call server.app:create_app"]
