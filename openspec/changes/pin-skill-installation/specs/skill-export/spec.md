# Spec Delta

## Purpose

Export standalone agent instructions with installation guidance that matches the installed DressCode source when its exact revision is known.

## ADDED Requirements

### Requirement: Matching installation pin

`dresscode --skill` SHALL include a `uv tool install` command targeting `git+<repository-url>@<revision>` when installed-package metadata records a supported Git repository URL and a full resolved hexadecimal Git commit ID, without a `subdirectory` field. It SHALL use that source URL, including forks, and that commit rather than the caller's repository or a moving branch or tag. Setup SHALL explain how to install DressCode if it is missing. No manual SHA update SHALL be required.

#### Scenario: Installed official Git revision
- **WHEN** installed metadata records a supported official-repository Git URL and a full commit ID
- **THEN** exported Markdown contains the install command using that URL and pinned to that commit, even when invoked in an unrelated Git checkout

#### Scenario: Installed fork revision
- **WHEN** installed metadata records a supported fork Git URL and a full commit ID
- **THEN** exported Markdown contains the install command using the fork URL and that commit, not the official repository URL

### Requirement: Safe repository URL

Only credential-free HTTPS repository URLs with a host and repository path SHALL be supported. Malformed URLs and URLs with queries, fragments, whitespace, control characters or backticks SHALL fall back. When run, the generated command SHALL pass the complete Git source as one shell argument without executing URL content.

#### Scenario: Unsafe or unsupported source URL
- **WHEN** metadata contains credentials, a non-HTTPS URL, a malformed URL, a query, a fragment, whitespace, a control character or a backtick
- **THEN** export uses the fallback command without including that URL in the skill

#### Scenario: Shell metacharacters in a supported URL
- **WHEN** a supported repository URL contains shell metacharacters in its path
- **THEN** the generated command treats the complete Git source as one literal argument and the exported Markdown remains valid

### Requirement: Honest fallback

Without both a supported Git URL and a full resolved commit ID, export SHALL use the bundled Markdown unchanged. The bundled setup SHALL use `uv tool install 'git+https://github.com/Q-back/DressCode.git'`, with no revision pin or checkout assumption. This fallback SHALL NOT claim to match the installed version. Export SHALL NOT infer a revision from Git HEAD or add editable-specific installation guidance.

#### Scenario: No usable source metadata
- **WHEN** metadata is missing, unreadable, malformed, non-Git, has an unsupported URL, or lacks a full commit ID
- **THEN** export succeeds with the bundled Markdown and its official unpinned install command

#### Scenario: Metadata declares a package subdirectory
- **WHEN** installed metadata contains a `subdirectory` field, regardless of its value
- **THEN** export uses the bundled Markdown unchanged rather than generating a pin that targets the repository root

#### Scenario: Local install without Git source metadata
- **WHEN** DressCode runs from a local installation without a supported Git URL and resolved commit in its metadata, whether the checkout is clean or dirty
- **THEN** export uses the fallback command without deriving a revision from that checkout

### Requirement: Standalone read-only export

Skill export SHALL print plain Markdown to stdout and exit successfully without reading target-project configuration, invoking Git, or writing files. It SHALL work outside Git repositories and preserve the bundled skill's frontmatter and review instructions.

#### Scenario: Outside Git with broken configuration
- **WHEN** `dresscode --skill` runs outside Git with invalid project configuration and no Git executable available
- **THEN** it emits Markdown, leaves stderr empty, and changes no files or review state
