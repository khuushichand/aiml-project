SBOM
====

This folder stores generated CycloneDX SBOMs for the project.

Generate locally
----------------

- Prereqs: Python + pip, optional Node.js.
- Run: make sbom

Artifacts:
- sbom-python.cdx.json - Python deps from pyproject.toml (cdxgen) or requirements.txt fallback
- sbom-frontend.cdx.json - Node deps (if package-lock.json present)
- sbom.cdx.json - merged SBOM (if both present)

Validate and scan:
- make sbom-validate
- make sbom-scan   # requires grype

Notes
-----
- When pyproject.toml is present, the Makefile uses cdxgen to generate a Python SBOM without installing dependencies.
- If you prefer environment-resolved versions, create a venv (e.g., via uv sync) and run:
  - python -m pip install cyclonedx-py cyclonedx-cli
  - cyclonedx-py -e -o sbom/sbom-python.cdx.json
- For container/OS-level SBOMs, consider using syft:
  - syft dir:. -o cyclonedx-json=sbom/sbom-syft.cdx.json
  - syft <image> -o cyclonedx-json=sbom/sbom-image.cdx.json
