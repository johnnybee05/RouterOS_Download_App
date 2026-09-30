"""Český katalog. Zdrojový jazyk aplikace – tady texty vznikají."""

from __future__ import annotations


def plural_form(count: int) -> str:
    """Skloňování podle počtu: 1 soubor, 2 soubory, 5 souborů."""
    if count == 1:
        return "one"
    if 2 <= count <= 4:
        return "few"
    return "many"


MESSAGES: dict[str, str | dict[str, str]] = {
    # ------------------------------------------------------------------ #
    # Formáty a jednotky
    # ------------------------------------------------------------------ #
    "format.date": "%d.%m.%Y",
    "format.decimal": ",",
    "format.unknown": "—",
    "format.size_bytes": "{n} B",
    "format.duration_s": "{s} s",
    "format.duration_ms": "{m} min {s} s",
    "format.duration_hm": "{h} h {m} min",
    "count.files": {"one": "{n} soubor", "few": "{n} soubory", "many": "{n} souborů"},
    "count.packages": {
        "one": "{n} balíček",
        "few": "{n} balíčky",
        "many": "{n} balíčků",
    },
    "count.versions": {"one": "{n} verze", "few": "{n} verze", "many": "{n} verzí"},
    "count.architectures": {
        "one": "{n} architekturu",
        "few": "{n} architektury",
        "many": "{n} architektur",
    },
    # ------------------------------------------------------------------ #
    # Architektury
    # ------------------------------------------------------------------ #
    "arch.arm": "ARM (hAP ac², RB4011, CCR1009…)",
    "arch.arm64": "ARM64 (CCR2004, hAP ax³, RB5009…)",
    "arch.mipsbe": "MIPSBE (hEX, RB9xx, RB2011…)",
    "arch.mmips": "MMIPS (hAP lite, hEX S, RB750Gr3…)",
    "arch.smips": "SMIPS (hAP lite TC, mAP lite)",
    "arch.ppc": "PowerPC (RB1100, RB800 – starší)",
    "arch.tile": "Tile (CCR10xx, CCR11xx, CCR12xx)",
    "arch.x86": "x86 / CHR (PC, virtuální stroje)",
    # ------------------------------------------------------------------ #
    # Chyby jádra
    # ------------------------------------------------------------------ #
    "err.cancelled": "Operace byla zrušena.",
    "err.not_found": "Soubor nenalezen (404): {url}",
    "err.package_unavailable": (
        "Balíček „{package}“ pro verzi {version} a architekturu {arch} neexistuje."
    ),
    "err.http_status": "Server odpověděl {status}: {url}",
    "err.checksum_mismatch": (
        "Kontrolní součet nesouhlasí u {path}:\n"
        "  očekáváno {expected}\n  spočteno  {actual}"
    ),
    "err.size_mismatch": (
        "Velikost nesouhlasí u {path}: očekáváno {expected} B, staženo {actual} B."
    ),
    "err.connection_failed": "Spojení selhalo: {url}",
    "err.connection_failed_detail": "Spojení selhalo: {url}\n{detail}",
    "err.write_failed": "Chyba zápisu do {path}: {detail}",
    "err.transfer_interrupted": "Přenos {name} byl přerušen: {detail}",
    "err.invalid_version": "Neplatný tvar verze: {text}",
    "err.eocd_missing": "V konci archivu nebyl nalezen End of Central Directory záznam.",
    "err.zip64_out_of_tail": (
        "ZIP64 EOCD leží mimo stažený konec archivu – archiv je nestandardní."
    ),
    "err.cd_incomplete": (
        "Central Directory je neúplná: přečteno {read} z {expected} záznamů."
    ),
    "err.range_ignored": (
        "Server vrátil {got} B místo {expected} B Central Directory – "
        "Range není respektován."
    ),
    "err.zip64_locator_missing": "Archiv hlásí ZIP64, ale lokátor ZIP64 EOCD chybí.",
    "err.zip64_bad_signature": "Na pozici ZIP64 EOCD není očekávaná signatura.",
    "err.archive_unavailable": "Archiv není dostupný (HTTP {status}): {url}",
    "err.no_range_support": "Server nepodporuje Range požadavky: {url}",
    "err.newest_unexpected": "Nečekaný tvar odpovědi NEWEST: {text}",
    "err.newest_bad_version": "Nečekaný tvar verze v odpovědi NEWEST: {text}",
    "err.newest_wrong_major": (
        "Kanál vrátil verzi {version} (major {major}), očekáván major {expected}. "
        "Kanál pro tuto řadu neexistuje."
    ),
    "client.changelog_missing": "Pro verzi {version} není changelog k dispozici.",
    # ------------------------------------------------------------------ #
    # Stahování – hlášky do logu
    # ------------------------------------------------------------------ #
    "dl.already_downloaded": "{name}: už staženo, přeskočeno",
    "dl.existing_mismatch": "{name}: existující soubor nesouhlasí, stahuje se znovu",
    "dl.sha_verified": "{name}: SHA256 ověřeno",
    "dl.sha_unavailable": "{name}: SHA256 není k dispozici, ověřena velikost",
    "dl.retry": "{name}: spojení přerušeno, pokus {attempt} z {total}",
    "dl.resuming": "{name}: navazuji na rozdělané stahování ({bytes} B)",
    # ------------------------------------------------------------------ #
    # Aktualizace aplikace
    # ------------------------------------------------------------------ #
    "update.bad_response": "GitHub vrátil odpověď, které nerozumím.",
    "update.no_tag": "Vydání na GitHubu nemá značku verze.",
    "update.no_releases": "Projekt zatím nemá žádné vydání.",
    "update.rate_limited": (
        "GitHub teď další dotaz nepřijal – u nepřihlášených platí limit "
        "60 dotazů za hodinu. Zkus to za chvíli."
    ),
    "update.no_asset": (
        "Vydání neobsahuje soubor .exe – stáhni ho ručně ze stránky vydání."
    ),
    "update.transfer_interrupted": "Přenos se přerušil: {detail}",
    "update.missing_file": "Stažený soubor chybí: {path}",
    "update.backup_failed": (
        "Nepodařilo se odsunout původní soubor ({detail}).\n"
        "Spusť aplikaci ze složky, kam smíš zapisovat, nebo si novou verzi "
        "stáhni ručně ze stránky vydání."
    ),
    "update.deploy_failed": (
        "Novou verzi se nepodařilo nasadit ({detail}). Původní zůstala."
    ),
    "update.relaunch_failed": "Novou verzi se nepodařilo spustit: {detail}",
    # ------------------------------------------------------------------ #
    # GUI – nabídka
    # ------------------------------------------------------------------ #
    "menu.file": "&Soubor",
    "menu.open_target": "Otevřít cílovou složku",
    "menu.quit": "Ukončit",
    "menu.view": "&Zobrazení",
    "menu.theme": "Motiv",
    "menu.language": "Jazyk",
    "menu.help": "&Nápověda",
    "menu.check_updates": "Zkontrolovat aktualizace…",
    "menu.auto_updates": "Kontrolovat aktualizace při spuštění",
    "menu.releases": "Vydání na GitHubu",
    "menu.about": "O aplikaci",
    "theme.system": "Systém",
    "theme.light": "Světlý",
    "theme.dark": "Tmavý",
    "lang.system": "Podle systému",
    # ------------------------------------------------------------------ #
    # GUI – hlavní okno
    # ------------------------------------------------------------------ #
    "ui.window_title": "{app} – stahovač balíčků MikroTik RouterOS",
    "ui.series": "Řada:",
    "ui.channel": "Kanál:",
    "ui.version": "Verze:",
    "ui.version_tip": (
        "Vyber verzi ze seznamu, nebo ji napiš ručně (např. 7.20.3, 7.25beta5)."
    ),
    "ui.refresh": "Obnovit",
    "ui.refresh_tip": "Znovu načíst verze, balíčky a changelog",
    "ui.architectures": "Architektury",
    "ui.main_package": "Hlavní balíček",
    "ui.main_checkbox": "routeros (hlavní systém)",
    "ui.zip_checkbox": "Stáhnout celý archiv all_packages.zip",
    "ui.zip_tip": "Jeden ZIP se všemi extra balíčky pro danou architekturu.",
    "ui.extras": "Extra balíčky",
    "ui.filter_placeholder": "Filtr podle názvu…",
    "ui.select_all": "Vše",
    "ui.select_none": "Nic",
    "ui.changelog": "Changelog",
    "ui.target": "Cíl",
    "ui.folder": "Složka:",
    "ui.browse": "Procházet…",
    "ui.subfolder_version": "Podsložka <verze>",
    "ui.subfolder_arch": "Podsložka <architektura>",
    "ui.verify": "Ověřovat SHA256",
    "ui.verify_tip": (
        "MikroTik publikuje ke každému souboru sidecar .sha256. "
        "Bez ověření se kontroluje jen velikost."
    ),
    "ui.transfers": "Přenosy",
    "ui.log": "Log",
    "ui.download": "Stáhnout",
    "ui.cancel": "Zrušit",
    "ui.total_idle": "Celkem – nic se nestahuje",
    "ui.total_percent": "Celkem %p%",
    "ui.total_detail": "Celkem %p%  ({done} z {total})",
    "ui.choose_target": "Vyber cílovou složku",
    # Stavový řádek
    "status.ready": "Připraveno",
    "status.fetching_newest": "Zjišťuji nejnovější verzi ({channel})…",
    "status.searching_versions": "Hledám dostupné verze… {done}/{total}",
    "status.versions_available": "K dispozici {count}",
    "status.loading_packages": "Načítám balíčky pro {version}…",
    "status.packages_failed": "Balíčky se nepodařilo načíst",
    "status.pick_arch": "Vyber aspoň jednu architekturu",
    "status.no_match": "Filtru neodpovídá žádný balíček",
    "status.measuring": "Zjišťuji velikosti souborů…",
    "status.downloading_to": "Stahuji do {path}…",
    "status.cancelled": "Zrušeno",
    "status.download_cancelled": "Stahování zrušeno",
    "status.finished_with_errors": "Dokončeno s chybami",
    "status.done": "Hotovo",
    "status.download_failed": "Stahování selhalo",
    "status.load_error": "Chyba při načítání",
    "status.checking_updates": "Zjišťuji, jestli nevyšla nová verze…",
    "status.update_check_failed": "Aktualizace se nepodařilo zjistit",
    "status.up_to_date": "Verze {version} je nejnovější",
    "status.update_available": "K dispozici je verze {version}",
    # Popisky v panelech
    "ui.release_checking": "zjišťuji datum vydání…",
    "ui.release_unknown": "datum vydání se nepodařilo zjistit",
    "ui.release_missing": "datum vydání neuvedeno",
    "ui.released_on": "vydáno {date}",
    "ui.changelog_loading": "Načítám changelog…",
    "ui.changelog_error": "Chyba: {detail}",
    "ui.extras_hint": "Vyber verzi a architekturu – seznam se načte automaticky.",
    "ui.extras_summary": "{count} pro {archs}.",
    "ui.extras_failed": "Seznam balíčků se nepodařilo načíst. Zkus Obnovit.",
    "ui.missing_for": "chybí pro {archs}",
    "ui.missing_for_many": "chybí pro {count}",
    "ui.not_available_for": "Není k dispozici pro: {archs}",
    "ui.summary": "{files}, {size}",
    "ui.summary_unknown": "{files}, {size} + {n} neznámé velikosti",
    # Log
    "log.newest": "Nejnovější {channel}: {version} (vydáno {date})",
    "log.versions_failed": "Historii verzí se nepodařilo načíst: {detail}",
    "log.invalid_version": "Neplatný tvar verze: {text}",
    "log.packages_failed": "Balíčky pro {version}: {detail}",
    "log.packages_loaded": "{version}: načteno {count} extra ({source})",
    "log.source_zip": "z archivu all_packages",
    "log.source_head": "sondáží HEAD",
    "log.partials_cleaned": "Uklizeno {count} nedokončených .part z minulého běhu",
    "log.starting": "Stahuji {files} ({size}) do {path}",
    "log.file_done": "{name} – staženo",
    "log.cancelling": "Ruším stahování…",
    "log.cancelled_summary": (
        "Zrušeno. Dokončeno {done}, nedokončené soubory zůstaly jako .part "
        "a příště se na ně naváže."
    ),
    "log.finished_errors": "Dokončeno s chybami: {done} staženo, {failed} selhalo",
    "log.finished_ok": "Hotovo: {done} staženo, {skipped} přeskočeno",
    "log.update_skipped": "Verze {version} přeskočena.",
    "log.update_ready": "Nová verze čeká připravená v {path}",
    # Tabulka přenosů
    "transfer.file": "Soubor",
    "transfer.size": "Velikost",
    "transfer.status": "Stav",
    "transfer.progress": "Průběh",
    "transfer.pending": "čeká",
    "transfer.verifying": "ověřuji",
    "transfer.downloading": "stahuji",
    "transfer.done": "hotovo",
    "transfer.skipped": "přeskočeno",
    "transfer.failed": "chyba",
    "transfer.cancelled": "zrušeno",
    # Dialogy
    "dlg.closing_title": "Probíhá stahování",
    "dlg.closing_text": (
        "Stahování ještě běží. Opravdu ukončit?\n"
        "Rozdělané soubory zůstanou jako .part a příště se dopočítají."
    ),
    "dlg.nothing_title": "Není co stahovat",
    "dlg.nothing_text": "Zvol architekturu a aspoň jeden balíček.",
    "dlg.no_target_title": "Chybí cíl",
    "dlg.no_target_text": "Zadej cílovou složku.",
    "dlg.no_folder_title": "Složka neexistuje",
    "dlg.no_folder_text": "Složka {path} zatím neexistuje.",
    "dlg.update_title": "Aktualizace",
    "dlg.update_manual_ok": "Používáš nejnovější verzi ({version}).",
    "dlg.update_busy": (
        "K dispozici je verze {version}.\n\n"
        "Teď se ale nevyměňuje – běží stahování balíčků. Až doběhne, "
        "dej Nápověda → Zkontrolovat aktualizace."
    ),
    "dlg.update_relaunch_failed": (
        "{detail}\n\nNová verze je nasazená, jen ji spusť ručně."
    ),
    "dlg.install_title": "Nainstalovat aktualizaci",
    "dlg.install_text": (
        "Verze {version} je stažená a ověřená.\n\n"
        "Aplikace se teď ukončí a spustí znovu už v nové verzi. Pokračovat?"
    ),
    "dlg.about_title": "O aplikaci {app}",
    "dlg.about_text": (
        "<b>{app} {version}</b><br><br>"
        "Stahovač balíčků MikroTik RouterOS z oficiálních zdrojů "
        "(download.mikrotik.com).<br><br>"
        "Balíčky se ověřují proti SHA256 sidecarům, které MikroTik "
        "publikuje ke každému souboru.<br><br>"
        "Nastavení a cache: {path}"
    ),
    # ------------------------------------------------------------------ #
    # Okno aktualizace
    # ------------------------------------------------------------------ #
    "upd.title": "Aktualizace aplikace",
    "upd.heading": "K dispozici je verze {version}",
    "upd.current": "používáš {version}",
    "upd.published": "vydáno {date}",
    "upd.no_notes": "*Bez popisu.*",
    "upd.skip": "Přeskočit tuto verzi",
    "upd.skip_tip": (
        "Na tuhle verzi už aplikace sama neupozorní. Ručně ji zkontroluješ "
        "přes Nápověda → Zkontrolovat aktualizace."
    ),
    "upd.open_page": "Otevřít na GitHubu",
    "upd.close": "Zavřít",
    "upd.install": "Stáhnout a nainstalovat",
    "upd.retry": "Zkusit znovu",
    "upd.cancel_download": "Zrušit stahování",
    "upd.downloading": "Stahuji {name}…",
    "upd.verified": "Staženo a ověřeno.",
    "upd.cancelled": "Stahování zrušeno.",
    "upd.progress": "{done} z {total} (%p %)",
    "upd.no_asset_note": (
        "Vydání neobsahuje soubor .exe – stáhni si ho ze stránky vydání na GitHubu."
    ),
    "upd.source_note": (
        "Aplikace běží ze zdrojáků, ne z .exe – výměnu za sebe udělat nemůže. "
        "Aktualizuj přes „git pull“, nebo si stáhni .exe z GitHubu."
    ),
    # ------------------------------------------------------------------ #
    # Vlákna na pozadí
    # ------------------------------------------------------------------ #
    "worker.unexpected": "Neočekávaná chyba: {detail}",
    "worker.unexpected_download": "Neočekávaná chyba při stahování: {detail}",
    # ------------------------------------------------------------------ #
    # CLI
    # ------------------------------------------------------------------ #
    "cli.description": (
        "Stahovač balíčků MikroTik RouterOS (CLI k jádru GUI aplikace)."
    ),
    "cli.help.major": "řada RouterOS (výchozí 7)",
    "cli.help.channel": "kanál: stable, long-term, testing, development",
    "cli.help.lang": "jazyk výpisů: {codes} (výchozí podle systému)",
    "cli.help.no_cache": "ignorovat cache v %APPDATA%",
    "cli.help.newest": "nejnovější verze ve všech kanálech",
    "cli.help.versions": "historie verzí (sondáž přes CHANGELOG)",
    "cli.help.changelog": "changelog verze",
    "cli.help.changelog_version": "verze; výchozí je nejnovější v kanálu",
    "cli.help.packages": "seznam extra balíčků pro verzi a architekturu",
    "cli.help.urls": "vypsat URL bez stahování",
    "cli.help.download": "stáhnout balíčky",
    "cli.help.main": "hlavní balíček routeros",
    "cli.help.extra": "čárkou oddělené názvy, např. container,wifi-qcom",
    "cli.help.all_packages": "celý ZIP archiv",
    "cli.help.out": "cílová složka",
    "cli.help.per_version": "podsložka <verze>/",
    "cli.help.per_arch": "podsložka <arch>/",
    "cli.help.jobs": "souběžná stahování (výchozí 3)",
    "cli.help.no_verify": "neověřovat SHA256",
    "cli.help.self_update": "aktualizovat aplikaci z GitHubu",
    "cli.help.self_update_check": "jen zjistit, nestahovat",
    "cli.bad_channel": "neznámý kanál {value}; použij: {choices}",
    "cli.bad_arch": "neznámá architektura: {value}; k dispozici: {choices}",
    "cli.v6_channel": (
        "RouterOS v6 nemá kanál {channel}; k dispozici jsou jen stable a long-term."
    ),
    "cli.probing": "sondáž {done}/{total}",
    "cli.total_versions": "celkem {count}",
    "cli.source": "zdroj: {source}",
    "cli.missing_for_arch": "{name}: pro {arch} neexistuje",
    "cli.skipped_missing": "balíček {item} pro tuto verzi neexistuje, přeskočen",
    "cli.nothing_to_download": (
        "Nic k stažení – zvol --main, --extra nebo --all-packages."
    ),
    "cli.partials_cleaned": "uklizeno {count} nedokončených .part souborů",
    "cli.plan": "{version}: {files}, přibližně {size} -> {path}",
    "cli.cancelled_by_user": "Zrušeno uživatelem.",
    "cli.cancelled": "Zrušeno.",
    "cli.summary": "Hotovo: {done} staženo, {skipped} přeskočeno, {failed} selhalo",
    "cli.error": "Chyba: {detail}",
    "cli.downloading": "stahuji {text}",
    "cli.of_total": "{done} z {total}",
    "cli.update_current": "Verze {version} je nejnovější.",
    "cli.update_available": "K dispozici je {version} (používáš {current}).",
    "cli.update_published": "vydáno",
    "cli.update_page": "stránka",
    "cli.update_from_source": (
        "Aplikace běží ze zdrojáků – vyměnit se za sebe umí jen .exe.\n"
        "Stáhni si ho z {url}, nebo udělej git pull."
    ),
    "cli.update_installed": "Nasazeno. Původní verze odložena jako {name}.",
    "cli.update_restart": "Spusť aplikaci znovu.",
}
