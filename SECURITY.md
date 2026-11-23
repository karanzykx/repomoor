# Security policy

## Supported versions

The current public preview is v0.1.0. Security fixes should target the newest release; no long-term support commitment is established yet.

## Reporting a vulnerability

Please use GitHub's **Report a vulnerability** / private security advisory feature after the repository is created. Until private reporting is enabled, avoid posting working exploits, credentials, or sensitive project data in public issues. The project does not yet have an official security email.

Useful reports include a minimal synthetic repository, exact CLI invocation, OS/Python version, expected behavior, actual behavior, and whether a path outside the selected repo could have been accessed or changed.

## Threat model

Read `docs/SAFETY.md`. The project is not a security sandbox against concurrent malicious filesystem changes. It must not be run with elevated permissions against untrusted, attacker-controlled directories.
