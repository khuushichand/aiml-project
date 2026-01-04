FROM python:3.10-slim-bullseye

ARG USERNAME=devuser
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libmagic1 \
    portaudio19-dev \
    git \
    curl \
    ca-certificates \
    build-essential \
    sudo \
    zsh \
  && if ! getent group "$USER_GID" > /dev/null; then groupadd --gid "$USER_GID" "$USERNAME"; fi \
  && if ! id -u "$USERNAME" > /dev/null 2>&1; then useradd --uid "$USER_UID" --gid "$USER_GID" -m "$USERNAME"; fi \
  && echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/$USERNAME" \
  && chmod 0440 "/etc/sudoers.d/$USERNAME" \
  && rm -rf /var/lib/apt/lists/*

USER $USERNAME
