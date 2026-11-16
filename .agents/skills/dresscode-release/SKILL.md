---
name: dresscode-release
description: Prepare and tag a DressCode release. Use when asked to release DressCode, bump its version, or create a release tag.
---

# Release DressCode

Work from the repository root. Read `CHANGELOG.md`, `pyproject.toml`, and the
existing Git tags to choose the next version. Use the version policy in
`CHANGELOG.md`. From `1.0.0`, breaking changes require a major bump, compatible
features a minor bump, and compatible fixes a patch bump.

Treat CLI commands and options, JSON output, configuration, stored review data,
and the exported agent skill as public contracts. Call out breaking changes and
required migration steps in the release notes.

## Prepare the release

1. Check for unrelated working changes. Keep them out of the release commit.
2. Set the version in `pyproject.toml` and run `uv lock`. Verify the DressCode
   package version in `uv.lock` matches.
3. Check changes since the previous release tag against `Unreleased` notes.
   Record user-visible changes, not a raw commit log. Move the notes into a
   version heading dated `YYYY-MM-DD`; keep an empty `Unreleased` section.
4. Run these checks. Stop if any fails:

   ```sh
   uv run --locked pytest
   uv run --locked ruff check .
   uv run --locked ruff format --check .
   uv run --locked ty check
   ```

5. Follow the repository's `AGENTS.md` Review effort and hand-over requirements.
   Inspect the final diff and commit the release changes.

## Tag and hand over

From a clean checkout, create an annotated tag named `vMAJOR.MINOR.PATCH` on the
release commit. Its version must match `pyproject.toml` without the `v` prefix.
For example, for version `0.2.0`:

```sh
git tag -a v0.2.0 -m "Release 0.2.0"
```

Tags identify releases, not individual commits or merged pull requests. If the
tag already exists, report it and stop; never move or reuse a published tag.

Report the commit, tag, version, and check results. Push the release commit and
that specific tag only when the user has authorized publishing. Tagging alone
does not publish a package or create a GitHub Release.
