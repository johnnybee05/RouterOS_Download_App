"""English catalogue. Also the fallback for keys a translation is missing."""

from __future__ import annotations


def plural_form(count: int) -> str:
    """English has two forms: one file, two files."""
    return "one" if count == 1 else "other"


MESSAGES: dict[str, str | dict[str, str]] = {
    # ------------------------------------------------------------------ #
    # Formats and units
    # ------------------------------------------------------------------ #
    "format.date": "%Y-%m-%d",
    "format.decimal": ".",
    "format.unknown": "—",
    "format.size_bytes": "{n} B",
    "format.duration_s": "{s} s",
    "format.duration_ms": "{m} min {s} s",
    "format.duration_hm": "{h} h {m} min",
    "count.files": {"one": "{n} file", "other": "{n} files"},
    "count.packages": {"one": "{n} package", "other": "{n} packages"},
    "count.versions": {"one": "{n} version", "other": "{n} versions"},
    "count.architectures": {
        "one": "{n} architecture",
        "other": "{n} architectures",
    },
    # ------------------------------------------------------------------ #
    # Architectures
    # ------------------------------------------------------------------ #
    "arch.arm": "ARM (hAP ac², RB4011, CCR1009…)",
    "arch.arm64": "ARM64 (CCR2004, hAP ax³, RB5009…)",
    "arch.mipsbe": "MIPSBE (hEX, RB9xx, RB2011…)",
    "arch.mmips": "MMIPS (hAP lite, hEX S, RB750Gr3…)",
    "arch.smips": "SMIPS (hAP lite TC, mAP lite)",
    "arch.ppc": "PowerPC (RB1100, RB800 – legacy)",
    "arch.tile": "Tile (CCR10xx, CCR11xx, CCR12xx)",
    "arch.x86": "x86 / CHR (PCs, virtual machines)",
    # ------------------------------------------------------------------ #
    # Core errors
    # ------------------------------------------------------------------ #
    "err.cancelled": "The operation was cancelled.",
    "err.not_found": "File not found (404): {url}",
    "err.package_unavailable": (
        "Package “{package}” does not exist for version {version} "
        "and architecture {arch}."
    ),
    "err.http_status": "Server replied {status}: {url}",
    "err.checksum_mismatch": (
        "Checksum mismatch for {path}:\n"
        "  expected {expected}\n  computed {actual}"
    ),
    "err.size_mismatch": (
        "Size mismatch for {path}: expected {expected} B, downloaded {actual} B."
    ),
    "err.connection_failed": "Connection failed: {url}",
    "err.connection_failed_detail": "Connection failed: {url}\n{detail}",
    "err.write_failed": "Cannot write to {path}: {detail}",
    "err.transfer_interrupted": "Transfer of {name} was interrupted: {detail}",
    "err.invalid_version": "Malformed version: {text}",
    "err.eocd_missing": (
        "No End of Central Directory record was found at the end of the archive."
    ),
    "err.zip64_out_of_tail": (
        "The ZIP64 EOCD lies outside the downloaded tail – the archive is "
        "non-standard."
    ),
    "err.cd_incomplete": (
        "The Central Directory is incomplete: read {read} of {expected} records."
    ),
    "err.range_ignored": (
        "The server returned {got} B instead of {expected} B of the Central "
        "Directory – Range is not honoured."
    ),
    "err.zip64_locator_missing": (
        "The archive announces ZIP64 but the ZIP64 EOCD locator is missing."
    ),
    "err.zip64_bad_signature": (
        "No ZIP64 EOCD signature at the position the locator points to."
    ),
    "err.archive_unavailable": "Archive unavailable (HTTP {status}): {url}",
    "err.no_range_support": "Server does not support Range requests: {url}",
    "err.newest_unexpected": "Unexpected NEWEST response: {text}",
    "err.newest_bad_version": "Unexpected version in the NEWEST response: {text}",
    "err.newest_wrong_major": (
        "The channel returned version {version} (major {major}), expected major "
        "{expected}. This channel does not exist for that series."
    ),
    "client.changelog_missing": "No changelog is available for version {version}.",
    # ------------------------------------------------------------------ #
    # Downloads – log messages
    # ------------------------------------------------------------------ #
    "dl.already_downloaded": "{name}: already downloaded, skipped",
    "dl.existing_mismatch": "{name}: existing file does not match, downloading again",
    "dl.sha_verified": "{name}: SHA256 verified",
    "dl.sha_unavailable": "{name}: no SHA256 available, size verified instead",
    "dl.retry": "{name}: connection dropped, attempt {attempt} of {total}",
    "dl.resuming": "{name}: resuming an unfinished download ({bytes} B)",
    # ------------------------------------------------------------------ #
    # Application updates
    # ------------------------------------------------------------------ #
    "update.bad_response": "GitHub returned a response we cannot read.",
    "update.no_tag": "The GitHub release carries no version tag.",
    "update.no_releases": "The project has no releases yet.",
    "update.rate_limited": (
        "GitHub refused another request – anonymous callers get 60 requests "
        "per hour. Try again in a while."
    ),
    "update.no_asset": (
        "The release contains no .exe – download it manually from the release page."
    ),
    "update.transfer_interrupted": "The transfer was interrupted: {detail}",
    "update.missing_file": "The downloaded file is missing: {path}",
    "update.backup_failed": (
        "Could not move the original file aside ({detail}).\n"
        "Run the app from a folder you may write to, or download the new "
        "version manually from the release page."
    ),
    "update.deploy_failed": (
        "The new version could not be installed ({detail}). The original one stays."
    ),
    "update.relaunch_failed": "The new version could not be started: {detail}",
    # ------------------------------------------------------------------ #
    # GUI – menus
    # ------------------------------------------------------------------ #
    "menu.file": "&File",
    "menu.open_target": "Open target folder",
    "menu.quit": "Quit",
    "menu.view": "&View",
    "menu.theme": "Theme",
    "menu.language": "Language",
    "menu.help": "&Help",
    "menu.check_updates": "Check for updates…",
    "menu.auto_updates": "Check for updates at startup",
    "menu.releases": "Releases on GitHub",
    "menu.about": "About",
    "theme.system": "System",
    "theme.light": "Light",
    "theme.dark": "Dark",
    "lang.system": "System default",
    # ------------------------------------------------------------------ #
    # GUI – main window
    # ------------------------------------------------------------------ #
    "ui.window_title": "{app} – MikroTik RouterOS package downloader",
    "ui.series": "Series:",
    "ui.channel": "Channel:",
    "ui.version": "Version:",
    "ui.version_tip": (
        "Pick a version from the list, or type one (e.g. 7.20.3, 7.25beta5)."
    ),
    "ui.refresh": "Refresh",
    "ui.refresh_tip": "Reload versions, packages and the changelog",
    "ui.architectures": "Architectures",
    "ui.main_package": "Main package",
    "ui.main_checkbox": "routeros (main system)",
    "ui.zip_checkbox": "Download the whole all_packages.zip archive",
    "ui.zip_tip": "A single ZIP with every extra package for that architecture.",
    "ui.extras": "Extra packages",
    "ui.filter_placeholder": "Filter by name…",
    "ui.select_all": "All",
    "ui.select_none": "None",
    "ui.changelog": "Changelog",
    "ui.target": "Target",
    "ui.folder": "Folder:",
    "ui.browse": "Browse…",
    "ui.subfolder_version": "<version> subfolder",
    "ui.subfolder_arch": "<architecture> subfolder",
    "ui.verify": "Verify SHA256",
    "ui.verify_tip": (
        "MikroTik publishes a .sha256 sidecar next to every file. "
        "Without verification only the size is checked."
    ),
    "ui.transfers": "Transfers",
    "ui.log": "Log",
    "ui.download": "Download",
    "ui.cancel": "Cancel",
    "ui.total_idle": "Total – nothing is downloading",
    "ui.total_percent": "Total %p%",
    "ui.total_detail": "Total %p%  ({done} of {total})",
    "ui.choose_target": "Choose the target folder",
    # Status bar
    "status.ready": "Ready",
    "status.fetching_newest": "Looking up the newest version ({channel})…",
    "status.searching_versions": "Searching for available versions… {done}/{total}",
    "status.versions_available": "{count} available",
    "status.loading_packages": "Loading packages for {version}…",
    "status.packages_failed": "The package list could not be loaded",
    "status.pick_arch": "Pick at least one architecture",
    "status.no_match": "No package matches the filter",
    "status.measuring": "Measuring file sizes…",
    "status.downloading_to": "Downloading to {path}…",
    "status.cancelled": "Cancelled",
    "status.download_cancelled": "Download cancelled",
    "status.finished_with_errors": "Finished with errors",
    "status.done": "Done",
    "status.download_failed": "Download failed",
    "status.load_error": "Error while loading",
    "status.checking_updates": "Checking whether a new version is out…",
    "status.update_check_failed": "Could not check for updates",
    "status.up_to_date": "Version {version} is the newest one",
    "status.update_available": "Version {version} is available",
    # Panel labels
    "ui.release_checking": "looking up the release date…",
    "ui.release_unknown": "release date could not be determined",
    "ui.release_missing": "no release date given",
    "ui.released_on": "released {date}",
    "ui.changelog_loading": "Loading the changelog…",
    "ui.changelog_error": "Error: {detail}",
    "ui.extras_hint": "Pick a version and an architecture – the list loads itself.",
    "ui.extras_summary": "{count} for {archs}.",
    "ui.extras_failed": "The package list could not be loaded. Try Refresh.",
    "ui.missing_for": "missing for {archs}",
    "ui.missing_for_many": "missing for {count}",
    "ui.not_available_for": "Not available for: {archs}",
    "ui.summary": "{files}, {size}",
    "ui.summary_unknown": "{files}, {size} + {n} of unknown size",
    # Log
    "log.newest": "Newest {channel}: {version} (released {date})",
    "log.versions_failed": "The version history could not be loaded: {detail}",
    "log.invalid_version": "Malformed version: {text}",
    "log.packages_failed": "Packages for {version}: {detail}",
    "log.packages_loaded": "{version}: loaded {count} extra ({source})",
    "log.source_zip": "from the all_packages archive",
    "log.source_head": "by HEAD probing",
    "log.partials_cleaned": "Cleaned up {count} unfinished .part from a previous run",
    "log.starting": "Downloading {files} ({size}) to {path}",
    "log.file_done": "{name} – downloaded",
    "log.cancelling": "Cancelling the download…",
    "log.cancelled_summary": (
        "Cancelled. {done} finished; unfinished files stay as .part and will be "
        "resumed next time."
    ),
    "log.finished_errors": "Finished with errors: {done} downloaded, {failed} failed",
    "log.finished_ok": "Done: {done} downloaded, {skipped} skipped",
    "log.update_skipped": "Version {version} skipped.",
    "log.update_ready": "The new version is waiting in {path}",
    # Transfer table
    "transfer.file": "File",
    "transfer.size": "Size",
    "transfer.status": "Status",
    "transfer.progress": "Progress",
    "transfer.pending": "waiting",
    "transfer.verifying": "verifying",
    "transfer.downloading": "downloading",
    "transfer.done": "done",
    "transfer.skipped": "skipped",
    "transfer.failed": "failed",
    "transfer.cancelled": "cancelled",
    # Dialogs
    "dlg.closing_title": "Download in progress",
    "dlg.closing_text": (
        "A download is still running. Really quit?\n"
        "Unfinished files stay as .part and will be resumed next time."
    ),
    "dlg.nothing_title": "Nothing to download",
    "dlg.nothing_text": "Pick an architecture and at least one package.",
    "dlg.no_target_title": "Target missing",
    "dlg.no_target_text": "Enter a target folder.",
    "dlg.no_folder_title": "Folder does not exist",
    "dlg.no_folder_text": "The folder {path} does not exist yet.",
    "dlg.update_title": "Update",
    "dlg.update_manual_ok": "You are running the newest version ({version}).",
    "dlg.update_busy": (
        "Version {version} is available.\n\n"
        "It will not be installed now – a package download is running. "
        "Once it finishes, use Help → Check for updates."
    ),
    "dlg.update_relaunch_failed": (
        "{detail}\n\nThe new version is installed, just start it manually."
    ),
    "dlg.install_title": "Install the update",
    "dlg.install_text": (
        "Version {version} has been downloaded and verified.\n\n"
        "The app will now quit and start again in the new version. Continue?"
    ),
    "dlg.about_title": "About {app}",
    "dlg.about_text": (
        "<b>{app} {version}</b><br><br>"
        "Downloader for MikroTik RouterOS packages from the official sources "
        "(download.mikrotik.com).<br><br>"
        "Packages are verified against the SHA256 sidecars MikroTik publishes "
        "next to every file.<br><br>"
        "Settings and cache: {path}"
    ),
    # ------------------------------------------------------------------ #
    # Update window
    # ------------------------------------------------------------------ #
    "upd.title": "Application update",
    "upd.heading": "Version {version} is available",
    "upd.current": "you are running {version}",
    "upd.published": "released {date}",
    "upd.no_notes": "*No release notes.*",
    "upd.skip": "Skip this version",
    "upd.skip_tip": (
        "The app will not offer this version again by itself. You can still "
        "check manually via Help → Check for updates."
    ),
    "upd.open_page": "Open on GitHub",
    "upd.close": "Close",
    "upd.install": "Download and install",
    "upd.retry": "Try again",
    "upd.cancel_download": "Cancel download",
    "upd.downloading": "Downloading {name}…",
    "upd.verified": "Downloaded and verified.",
    "upd.cancelled": "Download cancelled.",
    "upd.progress": "{done} of {total} (%p %)",
    "upd.no_asset_note": (
        "The release contains no .exe – download it from the release page on GitHub."
    ),
    "upd.source_note": (
        "The app runs from source, not from an .exe, so it cannot replace itself. "
        "Update with “git pull”, or download the .exe from GitHub."
    ),
    # ------------------------------------------------------------------ #
    # Background workers
    # ------------------------------------------------------------------ #
    "worker.unexpected": "Unexpected error: {detail}",
    "worker.unexpected_download": "Unexpected error while downloading: {detail}",
    # ------------------------------------------------------------------ #
    # CLI
    # ------------------------------------------------------------------ #
    "cli.description": (
        "MikroTik RouterOS package downloader (CLI for the GUI application's core)."
    ),
    "cli.help.major": "RouterOS series (default 7)",
    "cli.help.channel": "channel: stable, long-term, testing, development",
    "cli.help.lang": "output language: {codes} (defaults to the system language)",
    "cli.help.no_cache": "ignore the cache in %APPDATA%",
    "cli.help.newest": "newest version in every channel",
    "cli.help.versions": "version history (probed via CHANGELOG)",
    "cli.help.changelog": "changelog of a version",
    "cli.help.changelog_version": "version; defaults to the newest in the channel",
    "cli.help.packages": "extra packages for a version and architecture",
    "cli.help.urls": "print URLs without downloading",
    "cli.help.download": "download packages",
    "cli.help.main": "the main routeros package",
    "cli.help.extra": "comma-separated names, e.g. container,wifi-qcom",
    "cli.help.all_packages": "the whole ZIP archive",
    "cli.help.out": "target folder",
    "cli.help.per_version": "<version>/ subfolder",
    "cli.help.per_arch": "<arch>/ subfolder",
    "cli.help.jobs": "parallel downloads (default 3)",
    "cli.help.no_verify": "do not verify SHA256",
    "cli.help.self_update": "update the application from GitHub",
    "cli.help.self_update_check": "only check, do not download",
    "cli.bad_channel": "unknown channel {value}; use one of: {choices}",
    "cli.bad_arch": "unknown architecture: {value}; available: {choices}",
    "cli.v6_channel": (
        "RouterOS v6 has no {channel} channel; only stable and long-term exist."
    ),
    "cli.probing": "probing {done}/{total}",
    "cli.total_versions": "{count} in total",
    "cli.source": "source: {source}",
    "cli.missing_for_arch": "{name}: does not exist for {arch}",
    "cli.skipped_missing": "package {item} does not exist for this version, skipped",
    "cli.nothing_to_download": (
        "Nothing to download – pick --main, --extra or --all-packages."
    ),
    "cli.partials_cleaned": "cleaned up {count} unfinished .part files",
    "cli.plan": "{version}: {files}, roughly {size} -> {path}",
    "cli.cancelled_by_user": "Cancelled by the user.",
    "cli.cancelled": "Cancelled.",
    "cli.summary": "Done: {done} downloaded, {skipped} skipped, {failed} failed",
    "cli.error": "Error: {detail}",
    "cli.downloading": "downloading {text}",
    "cli.of_total": "{done} of {total}",
    "cli.update_current": "Version {version} is the newest one.",
    "cli.update_available": "Version {version} is available (you run {current}).",
    "cli.update_published": "released",
    "cli.update_page": "page",
    "cli.update_from_source": (
        "The app runs from source – only an .exe can replace itself.\n"
        "Download it from {url}, or run git pull."
    ),
    "cli.update_installed": "Installed. The previous version was kept as {name}.",
    "cli.update_restart": "Start the application again.",
}
