# RosDownloader

**English** · [Čeština](README.cs.md)

A Windows desktop app that downloads **MikroTik RouterOS packages (`*.npk`)**
from MikroTik's official sources. Pick a series, a channel, a version, one or
more architectures and the packages you want — the app handles the rest,
SHA256 verification included.

![theme](docs/screenshot-dark.png)

## What it does

- **The newest version loads by itself** right after startup (v7 stable by default).
- Both the **v7 and v6** series, channels stable / long-term / testing / development
  (v6 only has stable and long-term — MikroTik publishes no more than that).
- **Version history** including betas and rcs, with the option to type a version by hand.
- **Several architectures at once** — the extra-package list is shown as a union,
  and each package says which architectures it is missing for.
- The extra-package list is discovered **dynamically**, not from a hardcoded list:
  an HTTP Range request reads just the tail of the `all_packages` archive
  (~66 kB instead of 50 MB).
- **SHA256 verification** of every file against the sidecar MikroTik publishes.
- Downloads into `.part`, **resumes interrupted transfers**, 3 files in parallel,
  3 attempts with a delay, a progress bar per file plus an overall one.
- **Updates itself from GitHub** — offers a new version, downloads it,
  verifies SHA256, and runs the new one after a restart.
- **Czech and English**, switchable while the app is running.
- **Theme switching on the fly** (System / Light / Dark), window title bar included.
- A panel with the changelog of the selected version.
- Settings and cache live in `%APPDATA%\RosDownloader\`.

## Installation

Download `RosDownloader.exe` from the [latest release](https://github.com/johnnybee05/RouterOS_Download_App/releases/latest)
and run it. A single file — **no Python installation** or anything else required.

Windows SmartScreen will most likely block it, because the file is **not signed
yet**. *More info → Run anyway*, or build it yourself following
[Building from source](#building-from-source) below.

The project is applying to [SignPath Foundation](https://signpath.org/) for a
free open-source code-signing certificate, and the release workflow already
submits every build for signing — so releases will carry a signature as soon as
it is approved. How that works, and the project's code signing policy, is in
[docs/CODE-SIGNING.en.md](docs/CODE-SIGNING.en.md).

Until then the SHA256 listed with the release is the check that matters
(afterwards, the signature is the stronger one):

```powershell
Get-FileHash .\RosDownloader.exe -Algorithm SHA256
Get-AuthenticodeSignature .\RosDownloader.exe | Format-List
```

## Usage

1. Top left, choose a **series** (v7 / v6) and a **channel**. The version fills in
   by itself; in the Version field you can pick an older one or type it
   (`7.20.3`, `7.25beta5`).
2. In the **Architectures** list tick one or more (`arm64`, `x86`, …).
   Not sure which? On the router run `/system resource print` and read the
   `architecture-name` line.
3. Leave **routeros (main system)** ticked and add extra packages
   (`container`, `wifi-qcom`, `user-manager`, …). The filter at the top searches
   by name; the **All** / **None** buttons tick whatever is currently visible.
4. At the bottom, enter the **target folder**. Optionally the files are sorted
   straight into `<target>\<version>\<architecture>\`.
5. **Download**. Progress is shown per file, with the overall bar and the speed
   at the bottom. **Cancel** stops it at any time — finished files stay,
   unfinished ones remain as `.part` and are resumed next time.

### Language

**View → Language**: System default / Čeština / English. With the default the app
follows the Windows UI language and falls back to English for anything it does not
speak. Switching takes effect immediately, without a restart, and the choice is
saved in the settings.

Log lines already written are left in the language they were written in — the log
records what happened, so it is not rewritten retroactively.

### Theme

**View → Theme**: System / Light / Dark. The default is System, where the app
follows the Windows setting and reacts to a change immediately, without a restart.
The choice is saved in the settings.

### Application updates

The app can update itself from
[GitHub Releases](https://github.com/johnnybee05/RouterOS_Download_App/releases).
A while after startup it quietly asks whether a newer version is out; if there is
none, or the request fails, it says nothing. Manually: **Help → Check for updates**.

When there is something to offer, a window opens with the release notes and four
options:

| Button | What it does |
|---|---|
| **Download and install** | downloads the `.exe`, verifies SHA256, and after confirmation quits the app and starts the new version |
| **Open on GitHub** | the release page in a browser, if you would rather download it manually |
| **Skip this version** | this version will not be offered again by itself (a manual check still shows it) |
| **Close** | it will be offered again next time |

The digest is taken from the `digest` field GitHub publishes with the asset,
otherwise from the `SHA256:` line in the release notes. If the digest or the size
does not match, the file is discarded and **nothing is replaced**.

The swap itself: Windows will not delete a running `.exe`, but it does allow
renaming it — the original is moved aside as `RosDownloader.exe.old` and the new
version takes its place. The app deletes the backup itself a few seconds after the
next start. If the swap fails halfway through, the original file is put back.

You can turn the quiet check off in **Help → Check for updates at startup**.
Running from source (`python main.py`) the app cannot replace itself — there it
only shows what is out and points to GitHub.

### Where things are stored

| File | Contents |
|---|---|
| `%APPDATA%\RosDownloader\settings.json` | last choices, target folder, theme, language, window geometry, update settings |
| `%APPDATA%\RosDownloader\versions.json` | cached version list (valid for 24 h) |
| `%APPDATA%\RosDownloader\packages.json` | cached package list for a version and architecture |

The **Refresh** button throws both caches away and loads everything again.

## CLI

The core can be driven without the GUI — handy for scripting and debugging:

```bash
python -m rosdl newest                          # newest version in every channel
python -m rosdl --major 6 newest
python -m rosdl versions                        # version history
python -m rosdl changelog 7.24.4
python -m rosdl packages --arch arm64           # extra packages for a version and architecture
python -m rosdl urls --arch arm64,x86 --main    # just print URLs, do not download
python -m rosdl download --arch arm64 --main --extra container,wifi-qcom --out D:\ros --per-version --per-arch
python -m rosdl self-update --check              # only check whether a new version is out
python -m rosdl self-update                      # download, verify and swap (from .exe only)
```

Useful switches: `--channel development`, `--lang cs|en`, `--no-cache` (global,
before the subcommand), `--jobs N`, `--no-verify`.

Without `--lang` the CLI uses the system language, same as the GUI. In a script
you can also force it with the `ROSDL_LANG` environment variable, which takes
precedence over the system setting:

```powershell
$env:ROSDL_LANG = "en"; python -m rosdl newest
```

## Building from source

You need **Python 3.12+ from python.org**. Python from the Microsoft Store is not
enough — PyInstaller cannot reach its files in `C:\Program Files\WindowsApps` and
the build fails; `build.ps1` warns about this itself.

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

The script creates `.venv`, installs the dependencies, runs the tests, generates
the icon and the file metadata, and builds `dist\RosDownloader.exe` (one file,
about 52 MB).

Switches: `-Clean` (from scratch), `-SkipTests`, `-Console` (a console variant for
debugging), `-Python <path>` (a specific interpreter), `-Upx` (UPX compression,
off by default — packed binaries are reported as suspicious by a large share of
antivirus engines, so the build asks for `--noupx` explicitly instead of leaving
it to whether `upx` happens to be on `PATH`).

A locally built `.exe` is **not signed** and SmartScreen will block it. Signed
binaries come only out of the release workflow —
see [docs/CODE-SIGNING.en.md](docs/CODE-SIGNING.en.md).

### Development

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m pytest tests -q
.\.venv\Scripts\python main.py          # the GUI from source
```

### Adding a language

Translations are plain Python modules, so PyInstaller bundles them without any
extra data files.

1. Copy `rosdl/i18n/en.py` to `rosdl/i18n/<code>.py`.
2. Translate the values in `MESSAGES` — leave the keys and the `{placeholders}`
   exactly as they are.
3. Adjust `plural_form()` to the rules of that language. It returns a form name
   (`one`, `few`, `many`, `other`) and every plural entry must have every form
   the function can return.
4. Add the code and its native name to `LANGUAGES` in `rosdl/i18n/__init__.py`.

`tests/test_i18n.py` then checks the new catalogue automatically: that no key is
missing, that the placeholders match the English original, and that the plurals
cover every form. English is the fallback, so a forgotten key shows the English
text rather than breaking the app.

## Project layout

```
rosdl/
  core/            the core, with no dependency on Qt
    urls.py        building URLs (v6/v7, x86 and powerpc rules)
    client.py      NEWEST, changelog, version history, package list
    zipindex.py    reading the ZIP Central Directory over HTTP Range
    downloader.py  downloading, .part, retries, SHA256
    updater.py     self-update from GitHub Releases
    config.py      settings in %APPDATA%
    cache.py       JSON cache with a TTL
  i18n/            translations, also without Qt
    __init__.py    lookup, plurals, detecting the system language
    cs.py, en.py   the catalogues
  gui/             PySide6
    theme.py       palettes, theme switching, dark title bar
    main_window.py the window
    update_dialog.py the new-version offer
    workers.py     background threads (QRunnable + signals)
    widgets.py     checkable list, transfer table, log
  cli.py           python -m rosdl
tests/             pytest with mocked HTTP
tools/             recon.py (endpoint verification), make_icon.py,
                   make_version_file.py (.exe metadata)
docs/            ENDPOINTS.md (cs) + ENDPOINTS.en.md – MikroTik's URL structure
                 CODE-SIGNING.md (cs) + .en.md – signing and the policy for it
build.ps1          building the .exe (unsigned)
.github/workflows/ tests.yml (tests), release.yml (release + signing)
```

All network traffic runs outside the GUI thread (`QThreadPool` + signals), so the
window does not freeze even while downloading a fifty-megabyte archive.

## Notes on MikroTik's sources

Details and evidence are in [docs/ENDPOINTS.en.md](docs/ENDPOINTS.en.md).
Three things catch out almost everyone who builds the URLs by eye:

- **v7 `x86` has no architecture suffix on the main package** — `routeros-7.24.4.npk`,
  while `routeros-7.24.4-x86.npk` is a 404.
- **v6 `x86` does have the suffix** — `routeros-x86-6.49.22.npk`.
- **v6 PowerPC is called `powerpc` in the main package**, but the archive and the
  extra packages use `ppc`.

The version list is discovered by probing `CHANGELOG`, because the
`mikrotik.com/download` page is a Livewire app that fetches the list over AJAX —
without a browser there is nothing to read out of the HTML.

## Licence

The application code is under the **MIT** licence — see [LICENSE](LICENSE).

The app only downloads files from MikroTik's public servers and does not modify
them in any way. The RouterOS packages themselves are covered by MikroTik's own
licence terms, which have nothing to do with this licence.

Libraries used: [PySide6](https://doc.qt.io/qtforpython/) (LGPLv3)
and [httpx](https://www.python-httpx.org/) (BSD-3-Clause). The built `.exe`
contains the Qt libraries dynamically linked under the terms of the LGPLv3.

## Credits

Free code signing provided by [SignPath.io](https://signpath.io/),
certificate by [SignPath Foundation](https://signpath.org/).
The project's code signing policy is in [docs/CODE-SIGNING.en.md](docs/CODE-SIGNING.en.md).
