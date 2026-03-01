ARG TLDW_AGENT_DIR=tldw-agent
ARG TLDW_SERVER_DIR=.

FROM golang:1.22 AS builder
ARG TLDW_AGENT_DIR
WORKDIR /src
COPY ${TLDW_AGENT_DIR}/ ./tldw-agent/
WORKDIR /src/tldw-agent
RUN go build -o /out/tldw-agent-acp ./cmd/tldw-agent-acp

FROM debian:bookworm-slim
ARG TLDW_SERVER_DIR
RUN apt-get update \
  && apt-get install -y --no-install-recommends openssh-server ca-certificates git bash python3 \
  && useradd -m -s /bin/bash acp \
  && chgrp root /home/acp \
  && chmod 0775 /home/acp \
  && rm -rf /var/lib/apt/lists/*

COPY --from=builder /out/tldw-agent-acp /usr/local/bin/tldw-agent-acp
COPY ${TLDW_SERVER_DIR}/Dockerfiles/ACP/entrypoint.sh /usr/local/bin/tldw-acp-entrypoint
RUN chmod +x /usr/local/bin/tldw-acp-entrypoint

EXPOSE 2222
ENTRYPOINT ["/usr/local/bin/tldw-acp-entrypoint"]
