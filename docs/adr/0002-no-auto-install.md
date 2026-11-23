# ADR 0002: Defer automatic third-party installers

**Status:** accepted | **Date:** 2026-11-18

## Context

The 19 projects expose varied scripts, hooks and MCP integrations. Some tool documentation uses setup flags implying local operation but can still modify user-level settings or depend on external binaries. Installing them automatically would violate the no-interference requirement.

## Decision

RepoMoor v0.1.0 never executes third-party installers, MCP binaries, package managers or arbitrary scripts. It produces recommendations and proposed evaluation steps only. Future adapters must show exactly what they would do and pass the safety matrix before shipping with execution capability.

## Consequences

The alpha cannot provide a fully automated 'one command installs everything' experience, but delivers trustworthy discovery, a reviewable plan, and a foundation for safe automation.
