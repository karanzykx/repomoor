# Security policy

## Supported versions

The current public preview is v0.1.0. Security fixes should target the newest release; no long-term support commitment is established yet.

## Reporting a vulnerability

Please report vulnerabilities privately with GitHub's **Report a vulnerability** button on the [Security tab](https://github.com/karanzykx/repomoor/security). Do not post working exploits, credentials or sensitive project data in public issues.

Useful reports include a minimal synthetic repository, exact CLI invocation, OS/Python version, expected behavior, actual behavior, and whether a path outside the selected repo could have been accessed or changed.

## Threat model

Read `docs/SAFETY.md`. The project is not a security sandbox against concurrent malicious filesystem changes. It must not be run with elevated permissions against untrusted, attacker-controlled directories.
