# Getting Started Guides

Choose your path based on what you want to accomplish:

| Guide | Time | Best For |
|-------|------|----------|
| [Tire Kicker](./Tire_Kicker.md) | 5-10 min | "I want to see if this works" |
| [Local Development](./Local_Development.md) | 15-30 min | "I'm building against the API" |
| [Docker Self-Host](./Docker_Self_Host.md) | 15-45 min | "I'm running this on my server" |
| [Production](./Production.md) | 1-2 hours | "I'm deploying for a team" |

## Quickest Path

```bash
git clone https://github.com/rmusser01/tldw_server.git && cd tldw_server
make quickstart
# Verify: curl http://localhost:8000/health
```

## Prerequisites

| Requirement | All Guides | Docker Guides |
|-------------|------------|---------------|
| Python 3.10+ | Required (except Docker) | Not needed |
| ffmpeg | Required (except Docker) | Not needed |
| Docker | Not needed | Required |
| Domain name | Not needed | Production only |

## Common Issues

See the troubleshooting section in each guide, or check:
- [README Troubleshooting](../../README.md#troubleshooting)
- [GitHub Issues](https://github.com/rmusser01/tldw_server/issues)
