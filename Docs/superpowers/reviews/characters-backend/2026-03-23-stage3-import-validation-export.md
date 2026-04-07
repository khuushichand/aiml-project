# Stage 3 Import, Validation, Image Handling, and Export

## Scope
- Reviewed the character import path, parser/validator split, image normalization, and export formats for CCv3, MIME detection, YAML/text fallback, and PNG embedding.
- Focused on whether invalid inputs are rejected consistently, whether image payloads are normalized safely, and whether exports can be re-imported without surprising mutation.
- Analysis-only review. No source code changes were made.

## Code Paths Reviewed
- `tldw_Server_API/app/api/v1/endpoints/characters_endpoint.py`
  - `_detect_mime_type()` and `_validate_file_type()` at `:31-126`
  - `POST /api/v1/characters/import` at `:754-890`
  - `_encode_png_with_chara_metadata()` at `:2927-2980`
  - `GET /api/v1/characters/{character_id}/export` at `:2983-3162`
- `tldw_Server_API/app/core/Character_Chat/ccv3_parser.py`
  - `validate_v3_card()` at `:17-32`
  - `parse_v3_card()` at `:35-64`
- `tldw_Server_API/app/core/Character_Chat/modules/character_io.py`
  - import caps and disallowed-pattern constants at `:65-163`
  - PNG metadata extraction at `:175-562`
  - JSON parsing dispatcher at `:576-742`
  - YAML/text fallback and image-only import helpers at `:745-946`
  - import/save dispatcher at `:949-1055`
- `tldw_Server_API/app/core/Character_Chat/modules/character_validation.py`
  - V2 structure validation at `:570-727`
  - character-book validation at `:423-567`
  - V2/V1 parse mapping at `:130-319`
- `tldw_Server_API/app/core/Character_Chat/modules/character_db.py`
  - image_base64 decode, verify, resize, and WEBP re-encode at `:30-180`
  - image load for UI helpers at `:380-407`

## Tests Reviewed
- `tldw_Server_API/tests/Characters/test_ccv3_parser.py`
  - Covers V3 happy path, missing required field rejection, and image field preservation.
  - Does not cover malformed JSON, invalid base64, or explicit V3 export/re-import round-trip.
- `tldw_Server_API/tests/Character_Chat/test_file_mime_detection.py`
  - Covers PNG/WEBP/JPEG signatures, JSON detection, text detection, extension mismatch rejection, and safe-extension constants.
  - Does not cover oversized upload rejection or endpoint-level 413 handling.
- `tldw_Server_API/tests/Character_Chat_NEW/unit/test_png_export.py`
  - Covers PNG embedding with and without a source image and verifies the `chara` tEXt payload round-trips.
  - Does not cover corrupt source PNGs or non-PNG source images.
- `tldw_Server_API/tests/Character_Chat_NEW/property/test_character_properties.py`
  - The round-trip import/export property test is present but skipped.
  - That leaves export/import preservation under-tested at the property level.
- `tldw_Server_API/tests/Characters/test_characters_endpoint.py`
  - Covers PNG import, YAML import, unsupported extension rejection, malformed YAML fallback to plain text, and V2 export.
  - Does not cover oversized uploads, invalid image payloads, or explicit CCv3 import via the endpoint.

## Validation Commands
- Targeted import/export test run:
```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/Characters/test_ccv3_parser.py \
  tldw_Server_API/tests/Character_Chat/test_file_mime_detection.py \
  tldw_Server_API/tests/Character_Chat_NEW/unit/test_png_export.py \
  tldw_Server_API/tests/Character_Chat_NEW/property/test_character_properties.py \
  tldw_Server_API/tests/Characters/test_characters_endpoint.py -k "import or export" -v
```
- Result: `9 passed, 1 skipped, 102 deselected`
- Direct parser and MIME detection run:
```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/Characters/test_ccv3_parser.py \
  tldw_Server_API/tests/Character_Chat/test_file_mime_detection.py -v
```
- Result: `46 passed`
- Bandit was requested in the task, but `python -m bandit` is not available in the current venv, so no security scan output was produced.

## Findings
- Medium | correctness | Malformed YAML and other non-JSON text are normalized into synthetic characters instead of being rejected.
  - `POST /api/v1/characters/import` accepts `.yaml`, `.yml`, `.txt`, and `.md` after `_validate_file_type()` classifies them as text or JSON-compatible content at `tldw_Server_API/app/api/v1/endpoints/characters_endpoint.py:91-126` and `:809-817`.
  - `load_character_card_from_string_content()` then falls back to a generated plain-text payload when JSON and YAML parsing fail at `tldw_Server_API/app/core/Character_Chat/modules/character_io.py:745-801`.
  - The endpoint test `test_import_malformed_yaml_falls_back_to_plain_text_character` at `tldw_Server_API/tests/Characters/test_characters_endpoint.py:1496-1516` confirms this behavior.
  - Impact: typoed or partially malformed card files import successfully as new synthetic characters, which is a validation contract surprise for callers who expected rejection.
- Medium | contract | Export is not lossless for missing `character_version` values.
  - V2 and V3 export branches synthesize `character_version` with a default of `"1.0"` when the stored record does not have one at `tldw_Server_API/app/api/v1/endpoints/characters_endpoint.py:3089` and `:3053`.
  - The PNG export path reuses the same V2 payload shape at `tldw_Server_API/app/api/v1/endpoints/characters_endpoint.py:3127-3147`.
  - Import parsers treat that field as real payload data and persist it on re-import at `tldw_Server_API/app/core/Character_Chat/ccv3_parser.py:40-59` and `tldw_Server_API/app/core/Character_Chat/modules/character_validation.py:172-189`.
  - Impact: a round-trip can mutate absent version metadata into an explicit `"1.0"` value, so exports are re-importable but not fully identity-preserving.
- Low | performance | Import and export image paths duplicate large payloads in memory instead of streaming or reusing buffers.
  - `POST /api/v1/characters/import` reads the entire upload into memory before type validation completes at `tldw_Server_API/app/api/v1/endpoints/characters_endpoint.py:794-812`.
  - When image data is normalized for storage, `_prepare_character_data_for_db_storage()` decodes the full base64 payload, verifies it with Pillow, opens it again for resize/WEBP conversion, and materializes a second in-memory output buffer at `tldw_Server_API/app/core/Character_Chat/modules/character_db.py:80-124`.
  - PNG export base64-encodes the full card JSON into a `chara` text chunk at `tldw_Server_API/app/api/v1/endpoints/characters_endpoint.py:2936-2944`, and JSON/V2 export base64-encodes the full character image again at `tldw_Server_API/app/api/v1/endpoints/characters_endpoint.py:3115-3121`.
  - Impact: the size cap limits worst-case memory growth, but large allowed images still incur multiple full-buffer copies and repeated transcode work per request.

## Coverage Gaps
- No direct test covers import size rejection at the endpoint boundary, including the `413 Request Entity Too Large` branch in `POST /import`.
- No direct test covers malformed or partial image payloads entering through the import endpoint, especially the distinction between MIME rejection and Pillow integrity rejection.
- The skipped property-based round-trip test leaves a broad gap around export/import stability across randomly generated card payloads.
- There is no direct test for explicit CCv3 import failure cases such as invalid top-level spec markers combined with malformed `data` content.

## Improvements
- Add a focused endpoint test for oversized imports so the size ceiling is documented as part of the public contract.
- Add one malformed-image import test for each supported image class to confirm the endpoint rejects invalid payloads before database insertion.
- Unskip or replace the round-trip property test with a deterministic export/import invariant test that exercises both V2 and PNG exports.
- If plain-text fallback is intentional, document it as a supported behavior so callers know malformed YAML is treated as a synthetic import rather than an error.
- If large-card export/import performance becomes user-visible, consider reducing duplicate full-buffer work in the image pipeline or documenting the memory tradeoff alongside the import size ceiling.

## Exit Note
- Stage 3 review completed against the requested import, validation, image-handling, and export surfaces.
- Targeted tests passed, and the only tooling gap was the unavailable `bandit` module in the local virtual environment.
- No source files were modified outside the owned Stage 3 report path.
