# Spec Delta

## Purpose

Export standalone agent instructions with installation guidance that matches the installed DressCode source when its exact revision is known.

## ADDED Requirements

### Requirement: Matching installation pin

`dresscode --skill` SHALL include `uv tool install "git+https://github.com/Q-back/DressCode.git@<revision>"` when installed-package metadata identifies a full resolved Git commit from that upstream repository. The revision SHALL identify the installed distribution, not the caller's repository. No manual SHA update SHALL be required.

#### Scenario: Installed upstream Git revision
- **WHEN** installed metadata records an upstream Git installation at a full commit ID
- **THEN** exported Markdown contains the install command pinned to that commit, even when invoked in an unrelated Git checkout

### Requirement: Honest fallback

When installed metadata cannot establish an exact upstream revision, skill export SHALL retain the bundled checkout-install instructions without adding a revision pin. Local and editable checkouts SHALL NOT acquire a pin from Git HEAD, even when the checkout is clean.

#### Scenario: No reliable upstream revision
- **WHEN** metadata is missing, unreadable, malformed, non-Git, from another repository, or lacks a full commit ID
- **THEN** export succeeds with the unmodified bundled Markdown and no invented pin

#### Scenario: Editable or dirty checkout
- **WHEN** DressCode runs from a local or editable checkout, whether clean or dirty
- **THEN** export retains the bundled checkout instructions without deriving a revision from that checkout

### Requirement: Standalone read-only export

Skill export SHALL print plain Markdown to stdout and exit successfully without reading target-project configuration, invoking Git, or writing files. It SHALL work outside Git repositories and preserve the bundled skill's frontmatter and review instructions.

#### Scenario: Outside Git with broken configuration
- **WHEN** `dresscode --skill` runs outside Git with invalid project configuration and no Git executable available
- **THEN** it emits Markdown, leaves stderr empty, and changes no files or review state
