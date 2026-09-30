"""CLI pro testování jádra bez GUI: ``python -m rosdl <příkaz>``."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from . import __version__
from .core import (
    ARCHITECTURES,
    CHANNELS_BY_MAJOR,
    RELEASES_PAGE_URL,
    CancelToken,
    Cancelled,
    Channel,
    Downloader,
    Http,
    Listener,
    MikrotikClient,
    RosdlError,
    Status,
    Version,
    check_for_update,
    download_update,
    install_update,
    is_frozen,
)
from .core.config import resolve_language
from .core.downloader import DownloadTask, build_tasks, cleanup_partials
from .core.util import files_count, human_size, human_speed, versions_count
from .i18n import LANGUAGES, set_language, t


class ConsoleListener(Listener):
    """Vypisuje průběh na jeden řádek na soubor."""

    def __init__(self, quiet: bool = False) -> None:
        self.quiet = quiet
        self._last_draw = 0.0

    def on_log(self, level: str, message: str) -> None:
        if self.quiet and level == "info":
            return
        prefix = {"info": "  ", "warning": "! ", "error": "X "}.get(level, "  ")
        print(f"\r{prefix}{message}".ljust(78), file=sys.stderr)

    def on_file_status(self, task: DownloadTask, status: Status) -> None:
        if status is Status.DOWNLOADING:
            print(f"-> {task.remote.name}", file=sys.stderr)

    def on_file_progress(
        self, task: DownloadTask, downloaded: int, total: int | None, speed: float
    ) -> None:
        now = time.monotonic()
        if now - self._last_draw < 0.2:
            return
        self._last_draw = now
        if total:
            pct = downloaded * 100 // total
            bar = "#" * (pct // 4) + "." * (25 - pct // 4)
            line = f"   [{bar}] {pct:3d}%  {human_speed(speed)}"
        else:
            line = f"   {human_size(downloaded)}  {human_speed(speed)}"
        print(f"\r{line}".ljust(78), end="", file=sys.stderr)

    def on_file_finished(self, result) -> None:  # noqa: ANN001 - FileResult
        mark = {
            Status.DONE: "OK",
            Status.SKIPPED: "--",
            Status.FAILED: "!!",
            Status.CANCELLED: "..",
        }.get(result.status, "??")
        print(
            f"\r{mark} {result.task.remote.name}"
            f"  {human_size(result.total)}".ljust(78),
            file=sys.stderr,
        )


# --------------------------------------------------------------------------- #
def _channel(value: str) -> Channel:
    try:
        return Channel(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            t(
                "cli.bad_channel",
                value=repr(value),
                choices=", ".join(c.value for c in Channel),
            )
        ) from exc


def _arch_list(value: str) -> list[str]:
    archs = [a.strip() for a in value.split(",") if a.strip()]
    unknown = [a for a in archs if a not in ARCHITECTURES]
    if unknown:
        raise argparse.ArgumentTypeError(
            t(
                "cli.bad_arch",
                value=", ".join(unknown),
                choices=", ".join(ARCHITECTURES),
            )
        )
    return archs


def _resolve_version(
    client: MikrotikClient, args: argparse.Namespace
) -> Version:
    if getattr(args, "version", None):
        parsed = Version.try_parse(args.version)
        if parsed is None:
            raise RosdlError(t("err.invalid_version", text=repr(args.version)))
        return parsed
    info = client.newest(args.major, args.channel)
    return info.version


# --------------------------------------------------------------------------- #
def cmd_newest(client: MikrotikClient, args: argparse.Namespace) -> int:
    channels = CHANNELS_BY_MAJOR[args.major]
    for channel in channels:
        try:
            info = client.newest(args.major, channel)
            print(f"{channel.value:<12} {info.version!s:<12} {info.released_text}")
        except RosdlError as exc:
            print(f"{channel.value:<12} — ({exc})")
    return 0


def cmd_versions(client: MikrotikClient, args: argparse.Namespace) -> int:
    newest = client.newest(args.major, args.channel).version

    def progress(done: int, total: int) -> None:
        print(
            "\r  " + t("cli.probing", done=done, total=total),
            end="",
            file=sys.stderr,
        )

    versions = client.list_versions(
        args.major, newest, use_cache=not args.no_cache, progress=progress
    )
    print("\r".ljust(30) + "\r", end="", file=sys.stderr)
    for version in versions:
        print(version)
    print(
        t("cli.total_versions", count=versions_count(len(versions))),
        file=sys.stderr,
    )
    return 0


def cmd_changelog(client: MikrotikClient, args: argparse.Namespace) -> int:
    print(client.changelog(_resolve_version(client, args)))
    return 0


def cmd_packages(client: MikrotikClient, args: argparse.Namespace) -> int:
    version = _resolve_version(client, args)
    for arch in args.arch:
        result = client.list_packages(version, arch, use_cache=not args.no_cache)
        print(f"\n{version} / {arch}  ({t('cli.source', source=result.source)})")
        main = client.main_file(version, arch)
        print(f"  {'[main]':<10} {main.name}")
        for name in result.packages:
            entry = result.entries[name]
            print(f"  {name:<18} {entry.filename:<38} {human_size(entry.size):>10}")
    return 0


def cmd_urls(client: MikrotikClient, args: argparse.Namespace) -> int:
    version = _resolve_version(client, args)
    for arch in args.arch:
        if args.main:
            print(client.main_file(version, arch).url)
        if args.all_packages:
            print(client.archive_file(version, arch).url)
        if args.extra:
            result = client.list_packages(version, arch, use_cache=not args.no_cache)
            for name in args.extra:
                entry = result.entries.get(name)
                if entry is None:
                    print(
                        "# " + t("cli.missing_for_arch", name=name, arch=arch),
                        file=sys.stderr,
                    )
                    continue
                print(client.extra_file(entry, version).url)
    return 0


def cmd_download(client: MikrotikClient, args: argparse.Namespace) -> int:
    version = _resolve_version(client, args)
    root = Path(args.out).expanduser()

    remotes = []
    missing: list[str] = []
    for arch in args.arch:
        if args.main:
            remotes.append(client.main_file(version, arch))
        if args.all_packages:
            remotes.append(client.archive_file(version, arch))
        if args.extra:
            result = client.list_packages(version, arch, use_cache=not args.no_cache)
            for name in args.extra:
                entry = result.entries.get(name)
                if entry is None:
                    missing.append(f"{name} ({arch})")
                    continue
                remotes.append(client.extra_file(entry, version))

    for item in missing:
        print("! " + t("cli.skipped_missing", item=item), file=sys.stderr)
    if not remotes:
        print(t("cli.nothing_to_download"), file=sys.stderr)
        return 2

    remotes = client.fill_sizes(remotes)
    removed = cleanup_partials(root)
    if removed:
        print(
            "  " + t("cli.partials_cleaned", count=len(removed)),
            file=sys.stderr,
        )

    tasks = build_tasks(
        root,
        remotes,
        per_version=args.per_version,
        per_arch=args.per_arch,
    )
    total = sum(t.remote.size or 0 for t in tasks)
    print(
        t(
            "cli.plan",
            version=version,
            files=files_count(len(tasks)),
            size=human_size(total),
            path=root,
        ),
        file=sys.stderr,
    )

    token = CancelToken()
    downloader = Downloader(
        client, max_workers=args.jobs, verify_sha256=not args.no_verify
    )
    try:
        report = downloader.run(tasks, ConsoleListener(quiet=args.quiet), token)
    except KeyboardInterrupt:
        token.cancel()
        print("\n" + t("cli.cancelled_by_user"), file=sys.stderr)
        return 130

    print(
        "\n"
        + t(
            "cli.summary",
            done=report.count(Status.DONE),
            skipped=report.count(Status.SKIPPED),
            failed=report.count(Status.FAILED),
        ),
        file=sys.stderr,
    )
    return 0 if report.ok else 1


# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m rosdl",
        description=t("cli.description"),
    )
    parser.add_argument(
        "--major", type=int, choices=(6, 7), default=7, help=t("cli.help.major")
    )
    parser.add_argument(
        "--channel",
        type=_channel,
        default=Channel.STABLE,
        help=t("cli.help.channel"),
    )
    parser.add_argument(
        "--lang",
        choices=tuple(LANGUAGES),
        help=t("cli.help.lang", codes=", ".join(LANGUAGES)),
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help=t("cli.help.no_cache").replace("%", "%%"),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("newest", help=t("cli.help.newest"))
    p.set_defaults(func=cmd_newest)

    p = sub.add_parser("versions", help=t("cli.help.versions"))
    p.set_defaults(func=cmd_versions)

    p = sub.add_parser("changelog", help=t("cli.help.changelog"))
    p.add_argument("version", nargs="?", help=t("cli.help.changelog_version"))
    p.set_defaults(func=cmd_changelog)

    p = sub.add_parser("packages", help=t("cli.help.packages"))
    p.add_argument("--version")
    p.add_argument("--arch", type=_arch_list, default=["arm64"])
    p.set_defaults(func=cmd_packages)

    p = sub.add_parser("urls", help=t("cli.help.urls"))
    p.add_argument("--version")
    p.add_argument("--arch", type=_arch_list, default=["arm64"])
    p.add_argument("--main", action="store_true")
    p.add_argument("--extra", type=lambda s: [x for x in s.split(",") if x], default=[])
    p.add_argument("--all-packages", action="store_true")
    p.set_defaults(func=cmd_urls)

    p = sub.add_parser("download", help=t("cli.help.download"))
    p.add_argument("--version")
    p.add_argument("--arch", type=_arch_list, default=["arm64"])
    p.add_argument("--main", action="store_true", help=t("cli.help.main"))
    p.add_argument(
        "--extra",
        type=lambda s: [x for x in s.split(",") if x],
        default=[],
        help=t("cli.help.extra"),
    )
    p.add_argument("--all-packages", action="store_true", help=t("cli.help.all_packages"))
    p.add_argument("--out", default=".", help=t("cli.help.out"))
    p.add_argument("--per-version", action="store_true", help=t("cli.help.per_version"))
    p.add_argument("--per-arch", action="store_true", help=t("cli.help.per_arch"))
    p.add_argument("--jobs", type=int, default=3, help=t("cli.help.jobs"))
    p.add_argument("--no-verify", action="store_true", help=t("cli.help.no_verify"))
    p.add_argument("--quiet", action="store_true")
    p.set_defaults(func=cmd_download)

    p = sub.add_parser("self-update", help=t("cli.help.self_update"))
    p.add_argument(
        "--check", action="store_true", help=t("cli.help.self_update_check")
    )
    p.set_defaults(func=cmd_selfupdate)

    return parser


def cmd_selfupdate(client: MikrotikClient, args: argparse.Namespace) -> int:
    """Aktualizace samotné aplikace z GitHub Releases."""
    release = check_for_update(client.http, __version__)
    if release is None:
        print(t("cli.update_current", version=__version__))
        return 0

    print(
        t("cli.update_available", version=release.version, current=__version__)
    )
    print(f"  {t('cli.update_published')}  {release.published_text}")
    print(f"  {t('cli.update_page')}  {release.page_url}")
    if args.check:
        return 0
    if not is_frozen():
        print(
            t("cli.update_from_source", url=RELEASES_PAGE_URL),
            file=sys.stderr,
        )
        return 1

    def progress(done: int, total: int | None) -> None:
        text = (
            t("cli.of_total", done=human_size(done), total=human_size(total))
            if total
            else human_size(done)
        )
        print(
            ("\r  " + t("cli.downloading", text=text)).ljust(48),
            end="",
            file=sys.stderr,
        )

    path = download_update(client.http, release, progress=progress)
    print(file=sys.stderr)
    backup = install_update(path)
    print(t("cli.update_installed", name=backup.name))
    print(t("cli.update_restart"))
    return 0


def _force_utf8_console() -> None:
    """Konzole na Windows má výchozí cp1250 – diakritika by se rozsypala."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def _preselect_language(argv: list[str] | None) -> None:
    """Nastaví jazyk dřív, než argparse složí nápovědu.

    ``--lang`` se proto čte ručně: kdyby se čekalo na ``parse_args``, byla
    by nápověda k ``--help`` už poskládaná v jazyce systému.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    chosen = ""
    for i, item in enumerate(args):
        if item == "--lang" and i + 1 < len(args):
            chosen = args[i + 1]
        elif item.startswith("--lang="):
            chosen = item.split("=", 1)[1]
    set_language(resolve_language(chosen))


def main(argv: list[str] | None = None) -> int:
    _force_utf8_console()
    _preselect_language(argv)
    args = build_parser().parse_args(argv)
    if args.major == 6 and args.channel not in CHANNELS_BY_MAJOR[6]:
        print(t("cli.v6_channel", channel=args.channel.value), file=sys.stderr)
        return 2

    with Http() as http:
        client = MikrotikClient(http)
        try:
            return args.func(client, args)
        except Cancelled:
            print("\n" + t("cli.cancelled"), file=sys.stderr)
            return 130
        except RosdlError as exc:
            print(t("cli.error", detail=exc), file=sys.stderr)
            return 1
