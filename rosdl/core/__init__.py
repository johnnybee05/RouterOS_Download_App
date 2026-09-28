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

__all__ = [
    "ARCHITECTURES",
    "CHANNELS_BY_MAJOR",
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
    "RemoteFile",
    "Report",
    "RosdlError",
    "Settings",
    "SizeMismatch",
    "Status",
    "Version",
    "ZipIndexError",
    "parse_changelog_date",
    "parse_newest",
]
