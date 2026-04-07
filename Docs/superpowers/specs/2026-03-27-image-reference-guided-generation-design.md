# Image Reference-Guided Generation Design

Date: 2026-03-27
Status: Approved for planning
Owner: Codex brainstorming session

## Summary

Extend the existing image-generation flow to support a single managed reference image for prompt-guided generation.

V1 keeps the current entry point, `POST /api/v1/files/create` with `file_type: "image"`, and adds one new optional payload field: `reference_file_id`.

When `reference_file_id` is absent, the request behaves exactly like today's text-to-image flow. When present, the request becomes reference-guided image generation and is allowed only when:

- the referenced file is a persisted, user-accessible managed image file
- the selected backend and model explicitly support reference-image input
- the referenced file passes type, size, and normalization rules

V1 is intentionally narrow:

- one reference image only
- tldw-managed files only
- API plus Playground modal support
- no multi-reference inputs
- no mask or inpainting
- no top-level reference strength control
- no silent fallback to text-to-image when a backend does not support the feature

## Problem

The repository already has a working image-generation stack centered on the file-artifacts API, backend adapters, and Playground request/event metadata. That stack is currently text-to-image first.

Users now need a way to generate a new image while using an existing image in their library as visual guidance. The main challenge is not adding another arbitrary provider parameter. The challenge is adding this capability in a way that is:

- explicit in the public API
- consistent across supported backends
- safe for user-owned managed files
- strict about unsupported backends and models
- compatible with existing artifact persistence and Playground flows

If reference-image input were introduced only as backend-specific `extra_params`, the feature would become hard to validate, hard to document, and easy to mislead users with. The system needs a first-class contract for the product feature while still allowing backend-specific request shaping internally.

## Goals

- Extend the existing image-generation path instead of creating a second image-generation subsystem.
- Support one managed reference image per request.
- Restrict V1 reference images to persisted, user-accessible managed image files.
- Add API support and Playground image-generation modal support in the same phase.
- Preserve current text-to-image behavior for requests without a reference image.
- Reject reference-image requests clearly when the selected backend or model does not support the capability.
- Introduce a shared normalization step so providers receive a consistent internal reference-image object.
- Preserve current output behavior: inline response bytes only, no generated-image byte persistence.
- Store enough reference provenance in artifact metadata to explain what source image was used.

## Non-Goals

- Supporting raw external URLs, arbitrary remote fetches, or client-supplied data URLs as reference inputs.
- Supporting reference images sourced from prior generated image artifacts unless those artifacts later gain durable stored bytes and eligibility rules.
- Supporting multiple reference images.
- Supporting inpainting, masking, outpainting, or image editing workflows as a separate mode.
- Adding a portable top-level `reference_strength` field in V1.
- Adding slash-command or general chat `/image` flows in V1.
- Creating a gallery, asset-management layer, or generated-image storage system.

## Current State

### Existing Image Generation Architecture

The backend already routes image generation through the file-artifacts system:

- image adapter normalization and validation in `app/core/File_Artifacts/adapters/image_adapter.py`
- shared image-generation request contract in `app/core/Image_Generation/adapters/base.py`
- backend adapters for stable-diffusion.cpp, SwarmUI, OpenRouter, Novita, Together, and Model Studio
- integration tests around `POST /api/v1/files/create` under `tests/Files`

The current backend request object is prompt-centric and does not carry a typed source-image concept.

### Existing UI Integration

The Playground image-generation flow already sends a structured request snapshot, including:

- prompt
- backend
- format
- size and sampling settings
- backend-specific `extraParams`

That request shape is mirrored in chat/image-generation event metadata used by the UI to show generation history and variants.

### Existing Artifact Persistence Rules

Current image-generation artifacts persist request metadata but do not persist generated image bytes server-side. Inline export bytes are returned to the caller and omitted on later artifact retrieval.

This matters for reference-image design because not every image artifact is automatically a valid future source image. V1 must define source eligibility separately instead of assuming every previous generated image can act as a durable managed source.

## User-Facing Scope

V1 reference-guided generation means:

- the user chooses one managed image they already own or can access
- the user writes a prompt describing the desired transformation or style direction
- the system generates a new image using that source image as visual guidance

The product promise is intentionally narrow. It does not promise strict editing semantics, localized masking, or a portable strength control across vendors. It promises that the chosen image is actually used when the backend claims support, and that the system rejects the request when it cannot honor that promise.

## Proposed Design

### 1. Public API Contract

Keep the existing endpoint:

- `POST /api/v1/files/create`

For `file_type: "image"`, extend the payload with one new optional field:

- `reference_file_id` (integer or string, following current file-id conventions)

Example request:

```json
{
  "file_type": "image",
  "title": "Watercolor poster variant",
  "payload": {
    "backend": "modelstudio",
    "prompt": "Turn this into a watercolor travel poster with clean typography space",
    "reference_file_id": 123,
    "model": "qwen-image",
    "width": 1024,
    "height": 1024
  },
  "export": {
    "format": "png",
    "mode": "inline",
    "async_mode": "sync"
  },
  "options": {
    "persist": true
  }
}
```

Behavior:

- If `reference_file_id` is omitted, the request is standard text-to-image.
- If `reference_file_id` is present, the request is reference-guided generation.
- Requests with `reference_file_id` must fail clearly when the referenced file is invalid, inaccessible, ineligible, or unsupported by the selected backend/model.

### 2. Eligible Reference Sources

V1 reference sources must satisfy all of the following:

- persisted in tldw-managed storage
- accessible to the current user under existing authorization rules
- identifiable as an image file by trusted metadata and validation
- retrievable as durable bytes at generation time

For V1, "managed image" should be interpreted narrowly. Eligible sources are:

- persisted uploaded image files already represented by the file-artifacts system or the underlying managed file store
- persisted image attachments whose bytes are durably retrievable through an existing server-side storage abstraction

Ineligible sources are:

- ephemeral inline-only generated image artifact bytes
- references that exist only inside chat event metadata
- attachments whose metadata exists but whose image bytes are not durably retrievable
- non-image managed files even if their preview UI renders a thumbnail

V1 explicitly excludes:

- external URLs
- raw data URLs
- ephemeral inline-only generated image artifact bytes
- non-image attachments

This keeps the security and storage model simple and avoids retrofitting the feature onto assets whose bytes are not durably available.

### 3. Internal Request Model

The public API should expose `reference_file_id`, but backend adapters should not resolve files or permissions on their own.

Add a typed internal object, for example:

```python
@dataclass(frozen=True)
class ResolvedReferenceImage:
    file_id: int | str
    filename: str | None
    mime_type: str
    width: int | None
    height: int | None
    bytes_len: int
    content: bytes | None
    temp_path: str | None
```

Then extend the shared image-generation request object with:

- `reference_image: ResolvedReferenceImage | None`

This preserves a clean boundary:

- public API stays simple
- file/artifact services handle lookup, auth, and normalization
- backend adapters consume a stable typed input instead of re-implementing file handling

The important design constraint is that adapters receive one normalized representation, not that the representation must always be fully resident in memory. The implementation may choose normalized bytes, a temp-file handle, or both, depending on provider transport and memory pressure.

### 4. Shared Reference-Image Resolution And Normalization

Before dispatching to a backend adapter, the file-artifacts image adapter should resolve and normalize the reference image through one shared path.

Responsibilities of that path:

- load the managed file using existing file ownership and access rules
- verify the file is a supported image type
- reject oversized or malformed inputs
- normalize orientation and strip problematic transport-specific metadata as needed
- flatten unsupported animated inputs if V1 chooses to allow them, or reject them explicitly
- optionally convert the source into a canonical transport-safe format for providers
- optionally downscale over-large sources according to config

The output of this step is the `ResolvedReferenceImage` object handed to the provider adapter.

This avoids backend drift. Without it, each adapter would make its own decisions about MIME validation, EXIF handling, resizing, and format conversion, which would create inconsistent behavior and test gaps.

### 5. Capability Model: Backend Plus Optional Model

Reference-image support must not be treated as a single backend-wide boolean.

Some providers may expose mixed support across models. For example:

- a backend may support text-to-image generally
- only some models under that backend may accept reference images

The capability contract should therefore resolve support using:

- backend
- optional selected model

Recommended capability surface:

- one authoritative backend-side capability resolver returns reference-image support semantics for `backend + model`
- provider/model listing should expose that resolved capability to the UI as a field such as `image_reference_input: true`
- if a provider cannot reliably declare model-specific support, the resolver should default to conservative rejection rather than optimistic acceptance

For V1, do not split the source of truth between UI heuristics, adapter-local logic, and handwritten frontend allowlists. The backend should own the capability decision and the UI should consume it.

If the current model-listing pipeline cannot express this cleanly for all providers on day one, a conservative backend config fallback is acceptable during implementation planning, but it must still feed one shared resolver rather than ad hoc checks in each consumer.

This keeps UI gating and API behavior aligned and avoids a false claim that "backend X supports references" when only one model on that backend actually does.

### 6. Artifact Metadata And Provenance

When a generation uses a reference image, the stored artifact metadata should preserve:

- `reference_file_id`
- a small immutable provenance snapshot, for example:
  - `reference_filename`
  - `reference_mime_type`
  - `reference_width`
  - `reference_height`

The artifact should not store:

- source image bytes
- normalized reference bytes
- generated image bytes beyond the existing inline response path

The provenance snapshot is useful even if the underlying managed file is later renamed, moved, or removed. A plain file id alone is not enough context for debugging or auditability.

### 7. Backend Adapter Responsibilities

Each backend adapter that supports reference-image generation should translate the shared `ResolvedReferenceImage` into the provider's required transport format. That may be:

- multipart upload
- base64 field
- nested content array
- provider-specific input object

Provider adapters should not:

- decide whether the user may access the source file
- retrieve managed files directly from the database
- invent their own validation rules for source file eligibility

For unsupported adapters, requests containing `reference_image` should fail with a clear capability error before any upstream request is attempted.

### 8. Error Model

V1 should add explicit error cases instead of collapsing all failures into `image_params_invalid`.

Recommended new errors:

- `reference_image_not_found`
- `reference_image_access_denied`
- `reference_image_not_image`
- `reference_image_too_large`
- `reference_image_invalid`
- `reference_image_unsupported_by_backend`
- `reference_image_unsupported_by_model`

Security note:

- in multi-user mode, external responses may intentionally collapse `reference_image_not_found` and `reference_image_access_denied` into a single safe user-visible error to avoid object enumeration
- internal logs and diagnostics may still preserve the more specific cause for operators and tests

Existing errors still apply:

- `image_backend_unavailable`
- `unsupported_export_format`
- `invalid_export_mode`
- `invalid_async_mode`
- `image_generation_failed`

These distinct errors matter for both API clients and Playground UX. The UI should be able to tell the user whether the problem is the chosen source file, permissions, file type, size limits, or provider capability.

### 9. Playground V1 UX

The Playground image-generation modal should add one optional control:

- `Reference image`

V1 UX requirements:

- allow generating without a reference image, preserving today's behavior
- allow choosing one eligible managed image as the reference
- only show eligible files in the picker, or clearly mark ineligible files as unavailable
- preserve the selected reference file in the structured request snapshot and image-generation event metadata
- respect backend/model capability when the user changes selections

Recommended behavior:

- when the selected backend/model does not support reference images, either disable the picker with an explanation or reject on submit with a clear error
- when a previously selected reference image becomes invalid for the current backend/model, show a visible warning and prevent misleading submission

V1 deliberately does not add:

- strength sliders
- mask editors
- multi-image arrangement controls
- generalized edit-mode switching

Implementation note for planning:

- the picker should not reimplement backend eligibility rules in the browser
- V1 should use either an eligibility-aware query source or a lightweight server validation path that the picker can rely on before submission

### 10. Event Metadata And Phase 2 Compatibility

The Playground request snapshot and event mirror payload should carry the selected reference id now, even though V1 only exposes the feature in the modal.

Add a field such as:

- `referenceFileId?: string | number`

to the request snapshot and any mirrored generation metadata used by the UI.

That keeps the event shape aligned with the artifact request shape and reduces rework when slash-command or chat `/image` flows are added in phase 2.

## Config And Limits

In addition to the current image-generation output controls, add input-side reference-image controls.

Recommended config additions under `[Image-Generation]`:

- `reference_image_enabled_backends` is not needed if capability is already derived from backend/model listings; avoid duplicate config unless implementation proves it necessary.
- `reference_image_max_bytes`
- `reference_image_max_pixels`
- `reference_image_allowed_mime_types`
- `reference_image_max_width`
- `reference_image_max_height`
- `reference_image_auto_downscale` (boolean)

These controls are separate from generated-image output limits. A source image may need stricter size and decoded-pixel caps than the generated result path.

## Security And Privacy

V1 deliberately chooses managed files only because this keeps the main risk surface tractable.

Security requirements:

- enforce existing authorization before loading source bytes
- do not permit arbitrary remote fetches through `reference_file_id`
- do not log source image bytes
- avoid logging full user prompts by default where existing image-generation rules already avoid that
- ensure temporary normalized reference buffers or files are request-scoped and cleaned up when disk staging is needed

Privacy requirements:

- source images remain user-owned assets governed by existing access controls
- normalized intermediate data should be treated as transient backend input material, not as a new user-facing stored asset

## Testing

### Backend Unit And Integration

- normalize payloads with and without `reference_file_id`
- reject nonexistent reference files
- reject inaccessible reference files
- reject non-image reference files
- reject oversized or malformed reference files
- verify reference provenance is stored in artifact metadata
- verify text-to-image behavior is unchanged when no reference is provided
- verify unsupported backends/models reject before upstream requests
- verify supported adapters receive the resolved internal reference-image object

### Adapter Tests

For each supporting adapter:

- confirm reference-image request mapping matches provider expectations
- confirm normalized bytes are encoded in the correct transport shape
- confirm unsupported models are rejected when the backend has mixed support

### UI Tests

- modal picker renders eligible managed images
- ineligible images are hidden or clearly marked unavailable
- selected reference image is included in the structured request snapshot
- backend/model capability changes clear or invalidate incompatible selections
- submit-time errors for invalid/unsupported reference inputs are surfaced clearly

## Rollout Strategy

### Phase 1

- backend contract and normalization
- provider/model capability plumbing
- one or more backend adapters with reference-image support
- Playground modal support

### Phase 2

- slash-command and chat `/image` entry points
- broader UI affordances built on the same request and event shape

This staged rollout keeps V1 small while preserving a path to the broader conversational image-generation UX later.

## Risks And Mitigations

### Risk: Source Eligibility Ambiguity

If "managed image" is not defined tightly, users will expect any image-like thing in the system to work as a source.

Mitigation:

- explicitly define eligible source types in the API spec and UI picker rules
- exclude inline-only generated artifacts in V1

### Risk: Capability Drift Across Providers

If support is tracked only at the backend level, model-specific limitations will leak through as runtime failures or silent prompt-only behavior.

Mitigation:

- model-aware capability resolution
- conservative rejection when support is unknown

### Risk: Backend Behavior Diverges

If each adapter normalizes reference images independently, behavior will become inconsistent.

Mitigation:

- central shared normalization layer
- typed `ResolvedReferenceImage`

### Risk: Users Believe the Reference Image Was Used When It Was Not

Silent fallback to text-to-image would undermine trust.

Mitigation:

- reject unsupported backend/model combinations
- expose capability state in UI

## Open Questions Deferred To Planning

- Which existing file-storage abstraction is the cleanest place to resolve managed reference bytes for image generation?
- Whether downscaling should be automatic by default or explicit when a source exceeds preferred dimensions.
- Which current backend should ship first for reference-image support based on real provider capability and implementation cost.
- Whether provenance should include a stable source content hash in addition to file metadata.

## Recommendation

Proceed with a single, explicit extension of the current image-generation contract:

- add `reference_file_id` publicly
- resolve it into a shared internal `ResolvedReferenceImage`
- gate support by backend plus model capability
- keep V1 API plus Playground only
- reject unsupported combinations clearly

This preserves the existing architecture, keeps the feature honest, and leaves room for later edit-mode and chat-surface expansion without over-designing V1.
