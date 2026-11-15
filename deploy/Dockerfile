# CodeGraph live demo: HydraDB (official image) + the CodeGraph UI server, in one container.
FROM ghcr.io/hydra-db/hydradb:0.4.0

USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip curl && \
    pip3 install --no-cache-dir --break-system-packages neo4j && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY codegraph/ /app/codegraph/
COPY rich_repo/ /app/rich_repo/
COPY Frontend/ /app/Frontend/
COPY start.sh /app/start.sh
# the platform may run the container as any user: keep app and data writable
RUN chmod +x /app/start.sh && chmod -R a+rwX /app

ENV PORT=7860 \
    CODEGRAPH_REPO=/app/rich_repo \
    CODEGRAPH_FRONTEND=/app/Frontend \
    CODEGRAPH_UI_HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1
EXPOSE 7860
ENTRYPOINT ["/app/start.sh"]
