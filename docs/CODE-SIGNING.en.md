# Code signing

**English** · [Čeština](CODE-SIGNING.md)

This document is both the project's **code signing policy** — SignPath
Foundation requires signed projects to publish one — and the description of
how signing is set up.

## Why

`RosDownloader.exe` is an unsigned file downloaded from the internet. Windows
knows where it came from (Mark-of-the-Web) and SmartScreen blocks it with
"Windows protected your PC", because there is no signature and no file
reputation to go by. Nothing fixes this except a **valid Authenticode
signature from a certificate authority Windows trusts** — a self-signed
certificate does nothing at all here, SmartScreen ignores such a signature.

Certificates cannot live in a repository or in the hands of a build running
on a laptop, and a commercial certificate costs hundreds of dollars a year.
So the project uses **[SignPath Foundation](https://signpath.org/)**, which
provides certificates to open-source projects free of charge and only signs
binaries it can itself verify were built from public sources.

## How it works

A signed `.exe` is produced **only** by
[`.github/workflows/release.yml`](../.github/workflows/release.yml) on a
GitHub-hosted runner:

1. The workflow runs on a `v*` tag.
2. It checks that the tag matches `rosdl.__version__`.
3. It builds the `.exe` with the same `build.ps1` used for local builds.
4. It uploads the unsigned `.exe` as a workflow artifact.
5. It submits that artifact to SignPath and waits for the result.
6. It verifies the signature with `Get-AuthenticodeSignature` — an invalid
   signature fails the build.
7. It attaches the signed `.exe` to the release (or opens a draft; release
   notes are written by hand).

SignPath asks GitHub itself which repository, commit and workflow run the
artifact came from (*origin verification*). One consequence is worth
remembering:

> **A manually built `.exe` uploaded to a release stays unsigned.**
> The only way to release is a tag that goes through the workflow.

Local `build.ps1` therefore does no signing at all, and says so when it
finishes.

### What gets signed

Only `RosDownloader.exe` built from the sources of this repository, from the
`main` branch, at a tagged version. Nothing else: no installers, no scripts,
no third-party binaries.

### Who can trigger a signature

Only a workflow run from this repository. In human terms, only whoever can
push a `v*` tag to the repository, i.e. the repository owner (johnnybee05).
The SignPath API token is stored as a GitHub secret and is never printed.

### How to verify a signature

```powershell
Get-AuthenticodeSignature .\RosDownloader.exe | Format-List
```

`Status` must be `Valid`, and the subject in `SignerCertificate` must be
**SignPath Foundation** — certificates from their programme name the
Foundation as the publisher, not the project author. Every release also
keeps its SHA256:

```powershell
Get-FileHash .\RosDownloader.exe -Algorithm SHA256
```

### If something is wrong

Suspected certificate misuse, or a signed binary that did not come from
here, belongs in
[issues](https://github.com/johnnybee05/RouterOS_Download_App/issues)
and at the same time with [SignPath](https://signpath.io/support), who will
revoke the certificate in such a case.

## Setup (one-off)

The workflow is written so that **while SignPath is not configured, the
signing step is skipped** and an unsigned `.exe` is released with a warning
in the log. Filling in the variables below turns signing on.

### 1. Apply for the programme

Applications go to <https://signpath.org/apply>. The conditions this project
meets: an OSI licence (MIT), a public repository, a fully automated build on
GitHub Actions, a download page describing the application, no proprietary
components. Approval takes days rather than hours.

### 2. Artifact configuration

`actions/upload-artifact` wraps the `.exe` in a ZIP, so the configuration on
the SignPath side has to expect a ZIP containing a single PE file:

```xml
<?xml version="1.0" encoding="utf-8"?>
<artifact-configuration xmlns="http://signpath.io/artifact-configuration/v1">
  <zip-file>
    <pe-file path="RosDownloader.exe">
      <authenticode-sign />
    </pe-file>
  </zip-file>
</artifact-configuration>
```

### 3. Variables and the secret in the repository

*Settings → Secrets and variables → Actions*:

| Name                                   | Kind     | Where from                            |
| -------------------------------------- | -------- | ------------------------------------- |
| `SIGNPATH_API_TOKEN`                   | secret   | SignPath → User → API tokens          |
| `SIGNPATH_ORGANIZATION_ID`             | variable | SignPath → Organization → ID          |
| `SIGNPATH_PROJECT_SLUG`                | variable | the project slug, e.g. `rosdownloader` |
| `SIGNPATH_SIGNING_POLICY_SLUG`         | variable | `release-signing`                     |
| `SIGNPATH_ARTIFACT_CONFIGURATION_SLUG` | variable | the configuration slug from step 2    |

`SIGNPATH_ORGANIZATION_ID` is the variable that switches the signing step
on — without it the step is skipped.

### 4. A dry run

The workflow can be started by hand (*Actions → release → Run workflow*).
Without a tag it releases nothing and just leaves the signed `.exe` as a
downloadable workflow artifact. For trials it is better to put
`test-signing` in `SIGNPATH_SIGNING_POLICY_SLUG` — a test certificate will
not calm SmartScreen down, but it proves the whole path works.

## In the meantime

Until signing is in place, users are left with *More info → Run anyway* and
checking the hash. Two things can still be done about it, and the project
does them:

- **File metadata.** The `.exe` carries a VERSIONINFO resource (company,
  description, version, copyright) from
  [`tools/make_version_file.py`](../tools/make_version_file.py). Completely
  empty file properties are a signal to the heuristics in their own right.
- **No UPX.** `build.ps1` builds with `--noupx`, because packed binaries are
  reported as suspicious by a large share of antivirus engines. PyInstaller
  only reaches for UPX when it finds it on `PATH`, which made this depend on
  the machine doing the build; now it is asked for explicitly.

## Credits

Free code signing provided by [SignPath.io](https://signpath.io/),
certificate by [SignPath Foundation](https://signpath.org/).
