## Stage 1: Backend Allowlist + Data Model
**Goal**: Add allowed email domain support for org invites in schemas, repo, and service.
**Success Criteria**: Org invites persist allowed_email_domain and block redemption when email domain mismatches.
**Tests**: Add/update unit tests for org invite redemption allowlist.
**Status**: In Progress

## Stage 2: Org Invite Admin UI + Redeem Flow
**Goal**: Add admin WebUI for org invites and a public redeem page using preview + redeem endpoints.
**Success Criteria**: Admin can create/list/revoke org invites and copy links; users can preview and redeem in WebUI.
**Tests**: Manual WebUI smoke check.
**Status**: Not Started

## Stage 3: Docs Updates
**Goal**: Document org invite UI/redeem flow and allowlist behavior in the PRD.
**Success Criteria**: PRD reflects UI and allowlist behavior.
**Tests**: Docs review.
**Status**: Not Started
