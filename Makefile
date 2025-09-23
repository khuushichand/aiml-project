# Simple SBOM generation helpers

PY ?= python3
NPM ?= npm

.PHONY: sbom sbom-validate sbom-scan sbom-clean

sbom:
	@echo "==> Generating SBOMs into ./sbom"
	@mkdir -p sbom
	@if [ -f pyproject.toml ]; then \
		echo "==> pyproject.toml detected; using cdxgen (no install required)"; \
		npx -y @appthreat/cdxgen -t python -o sbom/sbom-python.cdx.json || true; \
	elif [ -f tldw_Server_API/requirements.txt ]; then \
		$(PY) -m pip install -q cyclonedx-bom cyclonedx-cli || true; \
		cyclonedx-bom -r tldw_Server_API/requirements.txt -o sbom/sbom-python.cdx.json || true; \
	else \
		echo "(info) No pyproject.toml or requirements.txt found; skipping Python SBOM"; \
	fi
	@echo "==> Generating Node/WebUI SBOM (if package-lock.json present)"
	@npx -y @cyclonedx/cyclonedx-npm --output-file sbom/sbom-frontend.cdx.json || true
	@echo "==> Generating source SBOM via syft (if installed)"
	@if command -v syft >/dev/null 2>&1; then \
		syft dir:. -o cyclonedx-json=sbom/sbom-syft.cdx.json || true; \
	else \
		echo "(info) syft not found; skip source SBOM. Install: https://github.com/anchore/syft"; \
	fi
	@echo "==> Merging (if multiple SBOMs present)"
	@files=""; \
	for f in sbom/sbom-python.cdx.json sbom/sbom-frontend.cdx.json sbom/sbom-syft.cdx.json; do \
		[ -f $$f ] && files="$$files $$f"; \
	done; \
	if [ -n "$$files" ]; then \
		cyclonedx-cli merge --input-files $$files --output-file sbom/sbom.cdx.json || cp sbom/sbom-python.cdx.json sbom/sbom.cdx.json || true; \
	else \
		echo "(warn) No component SBOMs generated; nothing to merge"; \
	fi
	@$(MAKE) sbom-validate || true
	@echo "==> Done. See ./sbom directory."

sbom-validate:
	@echo "==> Validating SBOM (if present)"
	@cyclonedx-cli validate --input-file sbom/sbom.cdx.json || true

sbom-scan:
	@echo "==> Vulnerability scan with grype (requires grype installed)"
	@grype sbom:sbom/sbom.cdx.json -o table || echo "(info) Install grype: https://github.com/anchore/grype"

sbom-clean:
	@rm -f sbom/*.cdx.json
	@echo "==> Cleaned ./sbom generated files"
