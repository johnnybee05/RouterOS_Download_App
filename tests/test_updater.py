"""Aktualizace z GitHub Releases: porovnání verzí, stažení, výměna souboru."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from rosdl.core.errors import (
    Cancelled,
    ChecksumMismatch,
    NetworkError,
    SizeMismatch,
    UpdateError,
)
from rosdl.core.http import CancelToken
from rosdl.core.updater import (
    LATEST_RELEASE_URL,
    AppVersion,
    ReleaseInfo,
    backup_path,
    check_for_update,
    cleanup_backups,
    download_update,
    fetch_latest,
    child_env,
    install_update,
    parse_release,
    relaunch,
)

from .conftest import FakeServer

ASSET_URL = "https://github.com/x/y/releases/download/v1.1.0/RosDownloader.exe"


def release_payload(
    tag: str = "v1.1.0",
    *,
    asset: bool = True,
    body: str = "Novinky.",
    digest: str | None = None,
    size: int = 12,
    assets: list | None = None,
) -> dict:
    payload: dict = {
        "tag_name": tag,
        "name": f"RosDownloader {tag.lstrip('v')}",
        "body": body,
        "html_url": f"https://github.com/x/y/releases/tag/{tag}",
        "published_at": "2026-09-28T09:40:53Z",
        "prerelease": False,
        "assets": [],
    }
    if assets is not None:
        payload["assets"] = assets
    elif asset:
        entry: dict = {
            "name": "RosDownloader.exe",
            "size": size,
            "browser_download_url": ASSET_URL,
        }
        if digest is not None:
            entry["digest"] = f"sha256:{digest}"
        payload["assets"] = [entry]
    return payload


def serve_release(server: FakeServer, payload: dict) -> None:
    server.add(LATEST_RELEASE_URL, json.dumps(payload))


# --------------------------------------------------------------------------- #
# Porovnání verzí
# --------------------------------------------------------------------------- #
class TestAppVersion:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("1.0.3", (1, 0, 3)),
            ("v1.0.3", (1, 0, 3)),
            ("  2.10  ", (2, 10)),
            ("3.0.0-beta.1", (3, 0, 0)),
            ("1.2.3+build7", (1, 2, 3)),
        ],
    )
    def test_parses(self, text: str, expected: tuple[int, ...]) -> None:
        assert AppVersion.parse(text).release == expected

    @pytest.mark.parametrize("text", ["", "nightly", "v", "1.0.x", "1..2"])
    def test_rejects_nonsense(self, text: str) -> None:
        assert AppVersion.try_parse(text) is None

    def test_orders_by_number_not_by_text(self) -> None:
        assert AppVersion.parse("1.0.10") > AppVersion.parse("1.0.9")

    def test_missing_parts_count_as_zero(self) -> None:
        assert AppVersion.parse("1.1") == AppVersion.parse("1.1.0")
        assert AppVersion.parse("1.1") < AppVersion.parse("1.1.1")

    def test_prerelease_goes_before_final(self) -> None:
        assert AppVersion.parse("2.0.0-rc.1") < AppVersion.parse("2.0.0")

    def test_prerelease_order_follows_semver(self) -> None:
        assert AppVersion.parse("2.0-beta.2") > AppVersion.parse("2.0-beta.1")
        assert AppVersion.parse("2.0-rc.1") > AppVersion.parse("2.0-beta.9")

    def test_str_is_the_input_back(self) -> None:
        assert str(AppVersion.parse("v1.0.3")) == "1.0.3"
        assert str(AppVersion.parse("2.0.0-beta.1")) == "2.0.0-beta.1"


# --------------------------------------------------------------------------- #
# Čtení odpovědi API
# --------------------------------------------------------------------------- #
class TestParseRelease:
    def test_reads_the_fields_we_show(self) -> None:
        info = parse_release(release_payload())
        assert info.tag == "v1.1.0"
        assert info.version == AppVersion.parse("1.1.0")
        assert info.asset_url == ASSET_URL
        assert info.asset_size == 12
        assert info.published_text == "28.09.2026"

    def test_takes_sha256_from_digest(self) -> None:
        info = parse_release(release_payload(digest="ab" * 32))
        assert info.asset_sha256 == "ab" * 32

    def test_falls_back_to_sha256_in_the_body(self) -> None:
        # Starší vydání pole `digest` nemají, otisk je jen v popisu.
        info = parse_release(release_payload(body=f"SHA256: {'cd' * 32}\n"))
        assert info.asset_sha256 == "cd" * 32

    def test_no_sha256_anywhere_is_not_an_error(self) -> None:
        assert parse_release(release_payload()).asset_sha256 is None

    def test_picks_the_exe_among_other_assets(self) -> None:
        info = parse_release(
            release_payload(
                assets=[
                    {"name": "notes.txt", "size": 1, "browser_download_url": "u1"},
                    {
                        "name": "RosDownloader.exe",
                        "size": 2,
                        "browser_download_url": "u2",
                    },
                ]
            )
        )
        assert info.asset_name == "RosDownloader.exe"
        assert info.asset_url == "u2"

    def test_release_without_exe_has_no_asset(self) -> None:
        info = parse_release(release_payload(asset=False))
        assert not info.has_asset

    def test_unparseable_tag_leaves_version_empty(self) -> None:
        assert parse_release(release_payload(tag="nightly")).version is None

    def test_missing_tag_is_an_error(self) -> None:
        with pytest.raises(UpdateError):
            parse_release({"name": "bez značky"})


# --------------------------------------------------------------------------- #
# Dotaz na GitHub
# --------------------------------------------------------------------------- #
class TestCheckForUpdate:
    def test_newer_release_is_offered(self, server: FakeServer) -> None:
        serve_release(server, release_payload("v1.1.0"))
        found = check_for_update(server.http(), "1.0.3")
        assert found is not None
        assert found.tag == "v1.1.0"

    def test_same_version_means_nothing_to_do(self, server: FakeServer) -> None:
        serve_release(server, release_payload("v1.0.3"))
        assert check_for_update(server.http(), "1.0.3") is None

    def test_older_release_is_ignored(self, server: FakeServer) -> None:
        serve_release(server, release_payload("v1.0.0"))
        assert check_for_update(server.http(), "1.0.3") is None

    def test_unparseable_tag_is_not_offered(self, server: FakeServer) -> None:
        serve_release(server, release_payload("nightly"))
        assert check_for_update(server.http(), "1.0.3") is None

    def test_sends_the_github_api_headers(self, server: FakeServer) -> None:
        serve_release(server, release_payload())
        check_for_update(server.http(), "1.0.3")
        request = server.requests[-1]
        assert request.headers["Accept"] == "application/vnd.github+json"
        assert request.headers["X-GitHub-Api-Version"] == "2022-11-28"

    def test_no_releases_yet_says_so(self, server: FakeServer) -> None:
        with pytest.raises(UpdateError, match="vydání"):
            fetch_latest(server.http())

    def test_rate_limit_explains_itself(self, server: FakeServer) -> None:
        serve_release(server, release_payload())
        server.fail_status = 403
        server.fail_times[LATEST_RELEASE_URL] = 1
        with pytest.raises(UpdateError, match="60 dotazů"):
            fetch_latest(server.http(attempts=1))

    def test_garbage_instead_of_json(self, server: FakeServer) -> None:
        server.add(LATEST_RELEASE_URL, "tohle není JSON")
        with pytest.raises(UpdateError):
            fetch_latest(server.http())


# --------------------------------------------------------------------------- #
# Stažení přílohy
# --------------------------------------------------------------------------- #
def exe_release(server: FakeServer, content: bytes, *, sha: bool = True) -> ReleaseInfo:
    server.add(ASSET_URL, content)
    digest = hashlib.sha256(content).hexdigest() if sha else None
    return parse_release(
        release_payload(digest=digest, size=len(content))
    )


class TestDownloadUpdate:
    def test_downloads_and_verifies(self, server: FakeServer, tmp_path: Path) -> None:
        content = b"nova verze" * 5000
        release = exe_release(server, content)
        path = download_update(server.http(), release, directory=tmp_path)
        assert path.read_bytes() == content
        assert path.name == "RosDownloader-v1.1.0.exe"

    def test_reports_progress(self, server: FakeServer, tmp_path: Path) -> None:
        content = b"x" * (700 * 1024)
        release = exe_release(server, content)
        seen: list[tuple[int, int | None]] = []
        download_update(
            server.http(),
            release,
            directory=tmp_path,
            progress=lambda done, total: seen.append((done, total)),
        )
        assert seen[0] == (0, len(content))
        assert seen[-1] == (len(content), len(content))

    def test_wrong_checksum_is_refused(
        self, server: FakeServer, tmp_path: Path
    ) -> None:
        server.add(ASSET_URL, b"podvrzeny soubor")
        release = parse_release(release_payload(digest="ab" * 32, size=16))
        with pytest.raises(ChecksumMismatch):
            download_update(server.http(), release, directory=tmp_path)
        assert list(tmp_path.iterdir()) == []

    def test_wrong_size_is_refused(self, server: FakeServer, tmp_path: Path) -> None:
        server.add(ASSET_URL, b"kratke")
        release = parse_release(release_payload(size=999))
        with pytest.raises(SizeMismatch):
            download_update(server.http(), release, directory=tmp_path)
        assert list(tmp_path.iterdir()) == []

    def test_broken_stream_is_retried(
        self, server: FakeServer, tmp_path: Path
    ) -> None:
        content = b"y" * (400 * 1024)
        release = exe_release(server, content)
        server.break_stream_after(ASSET_URL, 100 * 1024, times=1)
        path = download_update(
            server.http(), release, directory=tmp_path, attempts=2
        )
        assert path.read_bytes() == content

    def test_gives_up_after_the_last_attempt(
        self, server: FakeServer, tmp_path: Path
    ) -> None:
        content = b"z" * (400 * 1024)
        release = exe_release(server, content)
        server.break_stream_after(ASSET_URL, 50 * 1024, times=5)
        with pytest.raises(NetworkError):
            download_update(server.http(), release, directory=tmp_path, attempts=2)
        assert list(tmp_path.iterdir()) == []

    def test_cancel_stops_it(self, server: FakeServer, tmp_path: Path) -> None:
        release = exe_release(server, b"q" * 4096)
        token = CancelToken()
        token.cancel()
        with pytest.raises(Cancelled):
            download_update(
                server.http(), release, directory=tmp_path, token=token
            )

    def test_release_without_exe_cannot_be_downloaded(
        self, server: FakeServer, tmp_path: Path
    ) -> None:
        release = parse_release(release_payload(asset=False))
        with pytest.raises(UpdateError, match="ručně"):
            download_update(server.http(), release, directory=tmp_path)


# --------------------------------------------------------------------------- #
# Výměna běžícího souboru
# --------------------------------------------------------------------------- #
class TestInstallUpdate:
    def test_swaps_the_exe_and_keeps_a_backup(self, tmp_path: Path) -> None:
        exe = tmp_path / "RosDownloader.exe"
        exe.write_bytes(b"stara verze")
        new = tmp_path / "RosDownloader-v1.1.0.exe"
        new.write_bytes(b"nova verze")

        backup = install_update(new, exe)

        assert exe.read_bytes() == b"nova verze"
        assert backup.read_bytes() == b"stara verze"
        assert not new.exists()

    def test_overwrites_a_backup_from_last_time(self, tmp_path: Path) -> None:
        exe = tmp_path / "RosDownloader.exe"
        exe.write_bytes(b"v2")
        backup_path(exe).write_bytes(b"v0")
        new = tmp_path / "new.exe"
        new.write_bytes(b"v3")

        install_update(new, exe)

        assert exe.read_bytes() == b"v3"
        assert backup_path(exe).read_bytes() == b"v2"

    def test_missing_download_is_an_error(self, tmp_path: Path) -> None:
        exe = tmp_path / "RosDownloader.exe"
        exe.write_bytes(b"stara verze")
        with pytest.raises(UpdateError, match="chybí"):
            install_update(tmp_path / "neni.exe", exe)
        assert exe.read_bytes() == b"stara verze"

    def test_cleanup_removes_leftovers(self, tmp_path: Path) -> None:
        exe = tmp_path / "RosDownloader.exe"
        exe.write_bytes(b"verze")
        backup_path(exe).write_bytes(b"zbytek")
        (tmp_path / "RosDownloader.exe.1700000000.old").write_bytes(b"starsi zbytek")

        cleanup_backups(exe)

        assert exe.exists()
        assert list(tmp_path.iterdir()) == [exe]


# --------------------------------------------------------------------------- #
# Spuštění nové verze
# --------------------------------------------------------------------------- #
class TestChildEnv:
    def test_drops_the_unpacked_bundle(self) -> None:
        env = child_env(
            {
                "PATH": "C:/Windows",
                "_PYI_APPLICATION_HOME_DIR": "C:/Temp/_MEI123456",
                "_PYI_ARCHIVE_FILE": "C:/App/RosDownloader.exe",
                "_PYI_PARENT_PROCESS_LEVEL": "0",
                "_MEIPASS2": "C:/Temp/_MEI123456",
            }
        )

        assert env == {"PATH": "C:/Windows"}

    def test_keeps_everything_else(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ROSDL_TEST", "1")
        monkeypatch.setenv("_PYI_APPLICATION_HOME_DIR", "C:/Temp/_MEI123456")

        env = child_env()

        assert env["ROSDL_TEST"] == "1"
        assert "_PYI_APPLICATION_HOME_DIR" not in env


class TestRelaunch:
    def test_new_process_unpacks_its_own_folder(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Zděděná cesta do ``_MEIxxxxxx`` by novou verzi poškodila: starý
        proces tu složku při skončení maže."""
        exe = tmp_path / "RosDownloader.exe"
        exe.write_bytes(b"nova verze")
        monkeypatch.setenv("_PYI_APPLICATION_HOME_DIR", str(tmp_path / "_MEI123456"))
        monkeypatch.setenv("_PYI_ARCHIVE_FILE", str(exe))
        seen: dict = {}

        def fake_popen(args, **kwargs):
            seen["args"] = args
            seen["kwargs"] = kwargs
            return object()

        monkeypatch.setattr(subprocess, "Popen", fake_popen)

        relaunch(exe)

        assert seen["args"] == [str(exe)]
        env = seen["kwargs"]["env"]
        assert "_PYI_APPLICATION_HOME_DIR" not in env
        assert "_PYI_ARCHIVE_FILE" not in env

