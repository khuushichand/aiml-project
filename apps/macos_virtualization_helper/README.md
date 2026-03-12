# macOS Virtualization Helper

This directory reserves the native control-plane helper for the sandbox
`vz_linux` and `vz_macos` runtimes.

Current status:

- No native helper binary is implemented yet.
- The Python-side contract lives under
  `tldw_Server_API/app/core/Sandbox/macos_virtualization/`.
- In `TEST_MODE`, the helper client returns fake success responses so the
  sandbox runtime layers can be developed and tested without a real helper.

Planned responsibilities for the native helper:

- validate host and entitlement readiness
- create and boot VMs via Apple's `Virtualization.framework`
- manage guest control channels
- report structured lifecycle state back to the Python sandbox service
