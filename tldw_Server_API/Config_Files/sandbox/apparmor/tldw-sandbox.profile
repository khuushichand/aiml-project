# Example AppArmor profile for tldw sandbox containers.
#
# WARNING: This is a starting point only. Validate and tailor for your
# distribution and Docker configuration. Use at your own risk.

#include <tunables/global>

profile tldw-sandbox flags=(attach_disconnected,mediate_deleted) {
  # Base rules. See also: docker-default profile shipped by your distro.
  #include <abstractions/base>
  #include <abstractions/consoles>
  #include <abstractions/nameservice>

  # Deny potentially dangerous operations.
  deny ptrace peer=unconfined,
  deny mount,

  # Optional: deny all network by default (Docker --network none already enforces this)
  # Some AppArmor versions accept simple `deny network`, but behavior varies.
  # Uncomment cautiously if supported by your system:
  # deny network,

  # Allow typical file and process operations (delegated to includes + docker-default).
  file,
  capability,
}
