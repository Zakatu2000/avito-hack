FROM node:22-bookworm-slim AS webbuild
WORKDIR /app/web
COPY web/package*.json ./
RUN npm ci
COPY web ./
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY server/requirements.txt server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt
COPY server server
COPY ai ai
COPY --from=webbuild /app/web/dist web/dist
RUN useradd --uid 10001 --create-home buddy
USER buddy
EXPOSE 5050
CMD ["sh", "-c", "python -m server.store migrate && python -m server.store seed && exec python -m waitress --listen=0.0.0.0:5050 --call server.app:create_app"]

FROM runtime AS checks
ARG CHECK_UID=1000
ARG CHECK_GID=1000
ENV HOME=/tmp
USER root
COPY --from=webbuild /usr/local/bin/node /usr/local/bin/node
COPY --from=webbuild /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm
COPY --from=webbuild /app/web web
COPY server/requirements-test.txt server/requirements-test.txt
COPY contracts/requirements.txt contracts/requirements.txt
RUN pip install --no-cache-dir -r server/requirements-test.txt -r contracts/requirements.txt
COPY contracts contracts
COPY scripts scripts
COPY .coveragerc .coveragerc
RUN mkdir -p reports && chown -R "${CHECK_UID}:${CHECK_GID}" reports web
USER ${CHECK_UID}:${CHECK_GID}
CMD ["python", "scripts/check.py"]
