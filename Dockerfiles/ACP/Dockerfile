FROM golang:1.22 AS builder
WORKDIR /src
COPY tldw-agent/ ./tldw-agent/
WORKDIR /src/tldw-agent
RUN go build -o /out/tldw-agent-acp ./cmd/tldw-agent-acp

FROM debian:bookworm-slim
RUN apt-get update \
  && apt-get install -y --no-install-recommends openssh-server ca-certificates git bash \
  && rm -rf /var/lib/apt/lists/*

COPY --from=builder /out/tldw-agent-acp /usr/local/bin/tldw-agent-acp
COPY Dockerfiles/ACP/entrypoint.sh /usr/local/bin/tldw-acp-entrypoint
RUN chmod +x /usr/local/bin/tldw-acp-entrypoint

EXPOSE 22
ENTRYPOINT ["/usr/local/bin/tldw-acp-entrypoint"]
