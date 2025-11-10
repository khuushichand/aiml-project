SBOM
====

This folder stores generated CycloneDX SBOMs for the project.

Generate locally
----------------

- Prereqs: Python + pip, optional Node.js.
- Run: make sbom

Artifacts:
- sbom-python.cdx.json - Python deps from requirements.txt (CycloneDX)
- sbom-frontend.cdx.json - Node deps (if package-lock.json present)
- sbom.cdx.json - merged SBOM (if both present)

Validate and scan:
- make sbom-validate
- make sbom-scan   # requires grype

Notes
-----
- Python SBOMs are generated via the official CycloneDX Python CLI. Newer
  releases expose the `cyclonedx-py` CLI; older ones expose `cyclonedx-bom`.
  Either of the following works:
  - python -m pip install cyclonedx-bom
  - cyclonedx-py requirements -i tldw_Server_API/requirements.txt -o sbom/sbom-python.cdx.json
    # or (legacy)
  - cyclonedx-bom -r tldw_Server_API/requirements.txt -o sbom/sbom-python.cdx.json
- For container/OS-level SBOMs, consider using syft:
  - syft dir:. -o cyclonedx-json=sbom/sbom-syft.cdx.json
  - syft <image> -o cyclonedx-json=sbom/sbom-image.cdx.json
