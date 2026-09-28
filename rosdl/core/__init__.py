"""Jádro aplikace: zjišťování verzí, sestavování URL, stahování.

Tento balík záměrně nezávisí na Qt – dá se použít z CLI i z testů.
"""

from .client import (
    ChangelogInfo,
    MikrotikClient,
    NewestInfo,
    parse_changelog_date,
    parse_newest,
)
from .config import Settings
from .downloader import DownloadTask, Downloader, Listener, Report, Status
from .errors import (
    Cancelled,
    ChecksumMismatch,
    HttpError,
    NetworkError,
    NotFoundError,
    PackageNotAvailableError,
    RosdlError,
    SizeMismatch,
    UpdateError,
    ZipIndexError,
)
from .http import CancelToken, Http
from .models import (
    ARCHITECTURES,
    CHANNELS_BY_MAJOR,
    ArchPackages,
    Channel,
    PackageEntry,
    PackageKind,
    RemoteFile,
    Version,
)
from .updater import (
    RELEASES_PAGE_URL,
    AppVersion,
    ReleaseInfo,
    check_for_update,
    cleanup_backups,
    download_update,
    fetch_latest,
    install_update,
    is_frozen,
    relaunch,
)

__all__ = [
    "ARCHITECTURES",
    "CHANNELS_BY_MAJOR",
    "RELEASES_PAGE_URL",
    "AppVersion",
    "ArchPackages",
    "CancelToken",
    "ChangelogInfo",
    "Cancelled",
    "Channel",
    "ChecksumMismatch",
    "DownloadTask",
    "Downloader",
    "Http",
    "HttpError",
    "Listener",
    "MikrotikClient",
    "NetworkError",
    "NewestInfo",
    "NotFoundError",
    "PackageEntry",
    "PackageKind",
    "PackageNotAvailableError",
    "ReleaseInfo",
    "RemoteFile",
    "Report",
    "RosdlError",
    "Settings",
    "SizeMismatch",
    "Status",
    "UpdateError",
    "Version",
    "ZipIndexError",
    "check_for_update",
    "cleanup_backups",
    "download_update",
    "fetch_latest",
    "install_update",
    "is_frozen",
    "parse_changelog_date",
    "parse_newest",
    "relaunch",
]
