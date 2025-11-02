- Docker running (Docker Desktop or Colima)
  - act installed
      - macOS: brew install act
      - Linux: curl -s https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

  One-time config

  - Use the full Ubuntu image (has apt, Python, etc.) and works on Apple Silicon:
      - act -P ubuntu-latest=ghcr.io/catthehacker/ubuntu:full-22.04
  - Optional: enable debug
      - export ACTIONS_STEP_DEBUG=true

  Run jobs locally (CI workflow)

  - List jobs: act -l
  - Run linter (non-blocking mypy): act pull_request -j lint -P ubuntu-latest=ghcr.io/catthehacker/ubuntu:full-22.04
  - Run Ubuntu full suite (with Postgres; runs 3.11/3.12/3.13 matrix):
      - act pull_request -j full-suite-linux -P ubuntu-latest=ghcr.io/catthehacker/ubuntu:full-22.04
  - Run Windows/macOS full suite (simulated): act cannot run native Windows/macOS jobs. Use the Ubuntu job locally, and run macOS/Windows steps natively (see below).

  Notes for act

  - Services: Postgres service starts automatically; act exposes dynamic ports and we export them at runtime - no changes needed.
  - Network: Our composite actions fetch remote actions; ensure Docker has outbound network.
  - Artifacts: Use --artifact-server-path ./.act_artifacts to keep coverage/test XMLs locally.
  - Secrets: Not required for CI; if you want Codecov upload in local run (optional), pass -s CODECOV_TOKEN=....

  Run E2E smoke locally

  - This job is workflow_dispatch only. You can run it with:
      - act workflow_dispatch -j e2e-smoke -P ubuntu-latest=ghcr.io/catthehacker/ubuntu:full-22.04
  - It starts the server inside the runner container and hits it at 127.0.0.1 internally, so it doesn’t expose ports to your host.

  macOS/Windows jobs locally

  - act cannot emulate macOS/Windows runners.
  - For macOS (native):
      - brew install ffmpeg portaudio
      - python3.12 -m venv .venv && source .venv/bin/activate
      - pip install -U pip
      - pip install -e .[dev]
      - Env to mirror CI: export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 TEST_MODE=true DISABLE_HEAVY_STARTUP=1
      - Run tests: pytest -q -p pytest_cov --cov=tldw_Server_API --cov-report=term-missing
  - For Windows (native):
      - Install FFmpeg (choco) and consider PyAudioWPatch if PyAudio is painful:
          - py -3.12 -m venv .venv && .venv\Scripts\activate
          - pip install -e .[dev]
          - set PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 set TEST_MODE=true set DISABLE_HEAVY_STARTUP=1
          - pytest -q -p pytest_cov --cov=tldw_Server_API --cov-report=term-missing

  Helpful act commands

  - Dry run (plan only): act -n
  - Limit to one job: act pull_request -j full-suite-linux
  - Use a specific workflow file: act -W .github/workflows/ci.yml
  - Clean stuck containers: docker ps --filter name=act- -aq | xargs -r docker rm -f

  Common gotchas

  - Apple Silicon: use the full-22.04 image mapping above. If Docker defaults to arm64 and a step fails, try export DOCKER_DEFAULT_PLATFORM=linux/amd64.
  - Old act versions: ensure act ≥ 0.2.51 for good service container support (job.services.*).
  - Brew quirks on macOS: If PortAudio header errors persist, run brew update && brew install portaudio.
