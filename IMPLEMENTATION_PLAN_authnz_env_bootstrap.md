## Stage 1: Assess Current Initialize Flow
**Goal**: Identify how AuthNZ initialize handles .env discovery/validation and where it fails with missing SINGLE_USER_API_KEY.
**Success Criteria**: Clear plan for changes to env resolution, key generation, and persistence.
**Tests**: N/A (analysis only).
**Status**: Complete

## Stage 2: Implement Env Bootstrap + Key Persistence
**Goal**: Allow `python -m tldw_Server_API.app.core.AuthNZ.initialize` to create `tldw_Server_API/Config_Files/.env` if missing and write generated keys when required.
**Success Criteria**: Initialize can run without a pre-set SINGLE_USER_API_KEY, and generated keys are saved to the Config_Files .env.
**Tests**: Manual run of initialize in a fresh env (no SINGLE_USER_API_KEY) to confirm file creation and key write.
**Status**: Complete

## Stage 3: Verify Flow + Cleanup Messaging
**Goal**: Ensure validation happens after keys are written and messages guide users to the correct .env path.
**Success Criteria**: Initialize proceeds past environment checks and database setup with generated keys in place.
**Tests**: Rerun initialize after key generation; confirm no missing key errors.
**Status**: In Progress
