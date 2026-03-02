# Family Guardrails Wizard Guide

Use this guide when you want the fastest way to set up moderation guardrails for children or dependents in the WebUI or extension options page.

## Where to Open the Wizard

- WebUI: `Settings -> Family Guardrails Wizard`
- Extension options: `Settings -> Family Guardrails Wizard`

## Household Models Supported

- One guardian with multiple dependents
- Two guardians with shared dependents
- Institutional/caregiver setup

## Before You Start

- Multi-user mode should already be configured.
- Each guardian/dependent should have or be assigned an account user ID.
- Guardian and dependent relationships still require dependent acceptance to become active.

## Wizard Steps

1. **Household Basics**
   - Set household name.
   - Choose `Family` or `Institutional/Caregiver`.

2. **Add Guardians**
   - Add one or more guardians.
   - Include guardian display name and user ID.

3. **Add Dependents (Accounts)**
   - Add each dependent account.
   - Include dependent display name and user ID.

4. **Relationship Mapping**
   - Map each dependent to a guardian.
   - For shared households, map dependents to the responsible guardian.

5. **Templates + Customization**
   - Apply a template for each dependent (`Default Child Safe`, `Teen Balanced`, `School Research`).
   - Optionally open advanced overrides for action/notification context.

6. **Alert Preferences**
   - Choose default alert context (`topic_only`, `snippet`, or `full_message`).

7. **Invite + Acceptance Tracker**
   - Review queued vs active statuses.
   - Refresh to see updated acceptance/materialization state.

8. **Review + Activate**
   - Confirm guardian/dependent counts and activation summary.
   - Finish setup and return later for updates.

## Status Meanings

- **Queued until acceptance**: relationship exists but dependent has not accepted yet.
- **Active**: relationship accepted and queued plans were materialized into enforced supervised policies.
- **Failed**: plan activation failed; review template overrides and relationship state.

## Troubleshooting

- If relationship mapping fails, verify both guardian and dependent entries have valid user IDs.
- If plans remain queued, have the dependent sign in and accept the guardian relationship.
- If wizard endpoints are unavailable, verify your server exposes Guardian APIs and is up to date.

## Advanced Controls

After initial setup, use these for day-to-day management:

- `Settings -> Guardian & Monitoring`
- `Moderation Playground`
