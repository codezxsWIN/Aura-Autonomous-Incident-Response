# Changelog

All notable project changes are recorded here. The format follows the principles of [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), without assigning a release version before the project owner chooses one.

## Unreleased

### Added

- Persistent four-stage guided recovery director with elapsed time and retained evidence
- Opt-in receipt inspection after mandatory server-side verification
- Bounded replay waiting when a previous incident is still settling
- Exact-threshold regressions for Sentry admission and LangGraph routing
- GitHub community health files, issue forms, pull-request template, CI, and dependency updates

### Changed

- Guided recovery now announces work before it happens and reports concrete `503`, mutation, probe, retry, and receipt results
- The canonical system-fault threshold is inclusive at `0.800` across admission and graph routing
- The repository README is concise and routes detailed evidence into dedicated documentation

### Fixed

- Guided setup failures are no longer swallowed before a later timeout
- Receipt verification no longer closes or interrupts the completed walkthrough
- Checkout controls are restored after success, failure, and cancellation
- Minimal explicit browser telemetry no longer depends on incidental DOM mutation timing
- Immediate replay no longer fails on short-lived active-incident reset conflicts
