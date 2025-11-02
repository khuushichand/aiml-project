AppArmor profile (optional)
===========================

This directory contains an example AppArmor profile for the sandbox Docker containers.

Important notes:
- Loading AppArmor profiles requires root privileges and a Linux host with AppArmor enabled.
- Docker applies the `docker-default` profile by default. You may optionally load and use a hardened profile.
- To enable a custom profile, load it into the kernel and set `SANDBOX_DOCKER_APPARMOR_PROFILE` to the profile name.
- If the specified profile is not loaded, `docker create` fails. The sandbox runner will fall back automatically if supported.

Example usage:
1) Load profile:
   sudo apparmor_parser -r -W tldw-sandbox.profile

2) Set environment variable for the server:
   export SANDBOX_DOCKER_APPARMOR_PROFILE=tldw-sandbox

3) Start the server and run sandbox jobs as usual.

The `tldw-sandbox.profile` provided here is a conservative example. Review and adapt for your distro and Docker setup.
