# RosDownloader

[English](README.md) · **Čeština**

Desktopová aplikace pro Windows, která stahuje balíčky **MikroTik RouterOS (`*.npk`)**
z oficiálních zdrojů MikroTiku. Vybereš řadu, kanál, verzi, jednu nebo víc
architektur a balíčky – aplikace zbytek zařídí, včetně ověření SHA256.

![motiv](docs/screenshot-dark.png)

## Co umí

- **Nejnovější verze se načte sama** hned po spuštění (výchozí je v7 stable).
- Řady **v7 i v6**, kanály stable / long-term / testing / development
  (v6 má jen stable a long-term – víc jich MikroTik nepublikuje).
- **Historie verzí** včetně bet a rc, s možností napsat verzi ručně.
- **Více architektur naráz** – seznam extra balíčků se zobrazí jako sjednocení
  a u každého balíčku je vidět, pro které architektury chybí.
- Seznam extra balíčků se zjišťuje **dynamicky**, ne z pevného seznamu v kódu:
  přes HTTP Range se přečte jen konec archivu `all_packages` (~66 kB místo 50 MB).
- **Ověření SHA256** u každého souboru proti sidecaru, který MikroTik publikuje.
- Stahování do `.part`, **navazování na přerušené přenosy**, max 3 soubory naráz,
  3 pokusy s prodlevou, ukazatel průběhu pro každý soubor zvlášť i celkový.
- **Aktualizace sebe sama z GitHubu** – nabídne novou verzi, stáhne ji,
  ověří SHA256 a po restartu běží nová.
- **Česky i anglicky**, přepínání za běhu.
- **Změna motivu za běhu** (Systém / Světlý / Tmavý) včetně titulkového pruhu okna.
- Panel s changelogem vybrané verze.
- Nastavení a cache v `%APPDATA%\RosDownloader\`.

## Instalace

Stáhni `RosDownloader.exe` z [posledního releasu](https://github.com/johnnybee05/RouterOS_Download_App/releases/latest)
a spusť. Jeden soubor, **nepotřebuje nainstalovaný Python** ani nic dalšího.

Releasy jsou **podepsané** certifikátem Authenticode od
[SignPath Foundation](https://signpath.org/), která ho open-source projektům
dává zdarma. Na ověření je podpis, SHA256 uvedený u releasu zůstává jako
druhá možnost:

```powershell
Get-AuthenticodeSignature .\RosDownloader.exe | Format-List
Get-FileHash .\RosDownloader.exe -Algorithm SHA256
```

`Status` musí být `Valid` a certifikát uvádí jako vydavatele
**SignPath Foundation** – v jejich programu se podepisuje jejím jménem, ne
jménem autora projektu. Jak podepisování funguje a jaká jsou pravidla, je v
[docs/CODE-SIGNING.md](docs/CODE-SIGNING.md).

SmartScreen může u nové verze na prvních stažení ještě varovat, dokud si
soubor nevybuduje reputaci – *Více informací → Přesto spustit*. Podpisem
přestane být od neznámého vydavatele, reputace se ale počítá zvlášť.

## Použití

1. Vlevo nahoře zvol **řadu** (v7 / v6) a **kanál**. Verze se doplní sama,
   v poli Verze si můžeš vybrat starší nebo ji napsat ručně (`7.20.3`, `7.25beta5`).
2. V seznamu **Architektury** zaškrtni jednu nebo víc (`arm64`, `x86`, …).
   Nejsi si jistý? Na routeru `/system resource print`, řádek `architecture-name`.
3. Nech zaškrtnuté **routeros (hlavní systém)** a přidej extra balíčky
   (`container`, `wifi-qcom`, `user-manager`, …). Filtr nahoře hledá podle názvu,
   tlačítka **Vše** / **Nic** zaškrtnou to, co je zrovna vidět.
4. Dole zadej **cílovou složku**. Volitelně se soubory rovnou roztřídí
   do `<cíl>\<verze>\<architektura>\`.
5. **Stáhnout**. Průběh je vidět u každého souboru zvlášť, celkový ukazatel
   a rychlost jsou dole. **Zrušit** stahování kdykoli přeruší – hotové soubory
   zůstanou, nedokončené jako `.part` a příště se na ně naváže.

### Jazyk

**Zobrazení → Jazyk**: Podle systému / Čeština / English. Ve výchozím stavu se
aplikace řídí jazykem rozhraní Windows a u jazyka, který neumí, spadne do
angličtiny. Přepnutí se projeví hned, bez restartu, a volba se ukládá do nastavení.

Řádky, které už jsou v logu, zůstanou v jazyce, ve kterém se zapsaly – log je
záznam toho, co se stalo, takže se zpětně nepřepisuje.

### Motiv

**Zobrazení → Motiv**: Systém / Světlý / Tmavý. Výchozí je Systém, kdy aplikace
sleduje nastavení Windows a na jeho změnu reaguje okamžitě, bez restartu.
Volba se ukládá do nastavení.

### Aktualizace aplikace

Aplikace se umí aktualizovat sama z
[GitHub Releases](https://github.com/johnnybee05/RouterOS_Download_App/releases).
Chvíli po startu se tiše zeptá, jestli nevyšla novější verze; když ne nebo
když se dotaz nepovede, nedá o sobě vědět. Ručně: **Nápověda → Zkontrolovat
aktualizace**.

Když je co nabídnout, otevře se okno s popisem vydání a čtyřmi možnostmi:

| Tlačítko | Co udělá |
|---|---|
| **Stáhnout a nainstalovat** | stáhne `.exe`, ověří SHA256, po potvrzení ukončí aplikaci a spustí novou verzi |
| **Otevřít na GitHubu** | stránku vydání v prohlížeči, když si chceš stáhnout ručně |
| **Přeskočit tuto verzi** | na tuhle verzi už samo neupozorní (ruční kontrola ji ukáže dál) |
| **Zavřít** | nabídne se zas příště |

Otisk se bere z pole `digest`, které GitHub u přílohy publikuje, jinak
z řádku `SHA256:` v popisu vydání. Když otisk nebo velikost nesedí, soubor
se zahodí a **nic se nevyměňuje**.

Samotná výměna: Windows běžící `.exe` nesmaže, přejmenovat ho ale dovolí –
původní soubor se odsune jako `RosDownloader.exe.old` a na jeho místo přijde
nová verze. Zálohu aplikace smaže sama pár vteřin po příštím spuštění. Když
se výměna v půlce nepovede, původní soubor se vrátí zpátky.

Tichou kontrolu po startu vypneš v **Nápověda → Kontrolovat aktualizace při
spuštění**. Ze zdrojáků (`python main.py`) se aplikace vyměnit neumí – tam
jen ukáže, co vyšlo, a odkáže na GitHub.

### Kde se co ukládá

| Soubor | Obsah |
|---|---|
| `%APPDATA%\RosDownloader\settings.json` | poslední volby, cílová složka, motiv, jazyk, geometrie okna, nastavení aktualizací |
| `%APPDATA%\RosDownloader\versions.json` | cache seznamu verzí (platnost 24 h) |
| `%APPDATA%\RosDownloader\packages.json` | cache seznamu balíčků pro verzi a architekturu |

Tlačítko **Obnovit** obě cache zahodí a načte všechno znovu.

## CLI

Jádro jde ovládat i bez GUI – hodí se na skriptování a na ladění:

```bash
python -m rosdl newest                          # nejnovější verze ve všech kanálech
python -m rosdl --major 6 newest
python -m rosdl versions                        # historie verzí
python -m rosdl changelog 7.24.4
python -m rosdl packages --arch arm64           # extra balíčky pro verzi a architekturu
python -m rosdl urls --arch arm64,x86 --main    # jen vypsat URL, nestahovat
python -m rosdl download --arch arm64 --main --extra container,wifi-qcom --out D:\ros --per-version --per-arch
python -m rosdl self-update --check              # jen zjistit, jestli vyšla nová verze
python -m rosdl self-update                      # stáhnout, ověřit a vyměnit (jen z .exe)
```

Užitečné přepínače: `--channel development`, `--lang cs|en`, `--no-cache`
(globální, před podpříkazem), `--jobs N`, `--no-verify`.

Bez `--lang` se CLI řídí jazykem systému, stejně jako GUI. Ve skriptu se dá
vynutit i proměnnou prostředí `ROSDL_LANG`, která má před systémem přednost:

```powershell
$env:ROSDL_LANG = "en"; python -m rosdl newest
```

## Sestavení ze zdrojáků

Potřebuješ **Python 3.12+ z python.org**. Python z Microsoft Storu nestačí –
PyInstaller se nedostane k jeho souborům v `C:\Program Files\WindowsApps`
a build selže; `build.ps1` na to upozorní sám.

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

Skript vytvoří `.venv`, nainstaluje závislosti, pustí testy, vygeneruje ikonu
a metadata souboru a sestaví `dist\RosDownloader.exe` (jeden soubor, cca 52 MB).

Přepínače: `-Clean` (od nuly), `-SkipTests`, `-Console` (konzolová varianta
pro ladění), `-Python <cesta>` (konkrétní interpret), `-Upx` (komprese UPX,
ve výchozím stavu vypnutá – zabalené binárky hlásí jako podezřelé velká část
antivirů, takže si build říká o `--noupx` výslovně a nenechává to na tom,
jestli je `upx` náhodou v `PATH`).

Lokálně sestavený `.exe` **není podepsaný** a SmartScreen ho zablokuje.
Podepsané binárky vznikají jen ve vydávacím workflow – viz
[docs/CODE-SIGNING.md](docs/CODE-SIGNING.md).

### Vývoj

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m pytest tests -q
.\.venv\Scripts\python main.py          # GUI ze zdrojáků
```

### Přidání jazyka

Překlady jsou obyčejné Python moduly, takže je PyInstaller zabalí bez datových
souborů navíc.

1. Zkopíruj `rosdl/i18n/en.py` na `rosdl/i18n/<kód>.py`.
2. Přelož hodnoty v `MESSAGES` – klíče a `{placeholdery}` nech přesně tak, jak jsou.
3. Uprav `plural_form()` podle pravidel jazyka. Vrací název tvaru
   (`one`, `few`, `many`, `other`) a každý plurál musí mít všechny tvary,
   které funkce umí vrátit.
4. Přidej kód a jeho vlastní název do `LANGUAGES` v `rosdl/i18n/__init__.py`.

`tests/test_i18n.py` pak nový katalog zkontroluje sám: že nechybí klíč, že
placeholdery sedí s anglickým originálem a že plurály pokrývají všechny tvary.
Angličtina je záchranná síť, takže zapomenutý klíč ukáže anglický text,
ne rozbitou aplikaci.

## Struktura projektu

```
rosdl/
  core/            jádro bez závislosti na Qt
    urls.py        sestavování URL (pravidla v6/v7, x86, powerpc)
    client.py      NEWEST, changelog, historie verzí, seznam balíčků
    zipindex.py    čtení ZIP Central Directory přes HTTP Range
    downloader.py  stahování, .part, opakování, SHA256
    updater.py     vlastní aktualizace z GitHub Releases
    config.py      nastavení v %APPDATA%
    cache.py       JSON cache s TTL
  i18n/            překlady, také bez Qt
    __init__.py    hledání textů, plurály, zjištění jazyka systému
    cs.py, en.py   katalogy
  gui/             PySide6
    theme.py       palety, přepínání motivu, tmavý titulkový pruh
    main_window.py okno
    update_dialog.py nabídka nové verze
    workers.py     vlákna na pozadí (QRunnable + signály)
    widgets.py     seznam s checkboxy, tabulka přenosů, log
  cli.py           python -m rosdl
tests/             pytest s mockovaným HTTP
tools/             recon.py (ověření endpointů), make_icon.py,
                   make_version_file.py (metadata .exe)
docs/            ENDPOINTS.md + ENDPOINTS.en.md (en) – struktura URL MikroTiku
                 CODE-SIGNING.md + .en.md – podepisování a pravidla k němu
build.ps1          sestavení .exe (nepodepsané)
.github/workflows/ tests.yml (testy), release.yml (vydání + podpis)
```

Veškerá síťová komunikace běží mimo GUI vlákno (`QThreadPool` + signály),
takže okno nezamrzá ani při stahování padesátimegového archivu.

## Poznámky ke zdrojům MikroTiku

Podrobnosti a důkazy jsou v [docs/ENDPOINTS.md](docs/ENDPOINTS.md). Tři věci,
které zaskočí skoro každého, kdo si URL skládá podle oka:

- **v7 `x86` nemá v hlavním balíčku příponu architektury** – `routeros-7.24.4.npk`,
  zatímco `routeros-7.24.4-x86.npk` je 404.
- **v6 `x86` příponu naopak má** – `routeros-x86-6.49.22.npk`.
- **v6 PowerPC se v hlavním balíčku jmenuje `powerpc`**, ale archiv a extra
  balíčky používají `ppc`.

Seznam verzí se zjišťuje sondáží na `CHANGELOG`, protože stránka
`mikrotik.com/download` je Livewire aplikace, která seznam dotahuje až AJAXem –
bez prohlížeče se z HTML vyčíst nedá.

## Licence

Kód aplikace je pod licencí **MIT** – viz [LICENSE](LICENSE).

Aplikace jen stahuje soubory z veřejných serverů MikroTiku a nijak je
neupravuje. Na samotné balíčky RouterOS se vztahují licenční podmínky
MikroTiku, se kterými tato licence nemá nic společného.

Použité knihovny: [PySide6](https://doc.qt.io/qtforpython/) (LGPLv3)
a [httpx](https://www.python-httpx.org/) (BSD-3-Clause). Sestavené `.exe`
obsahuje Qt knihovny dynamicky linkované podle podmínek LGPLv3.

## Poděkování

Free code signing provided by [SignPath.io](https://signpath.io/),
certificate by [SignPath Foundation](https://signpath.org/).
Pravidla podepisování jsou v [docs/CODE-SIGNING.md](docs/CODE-SIGNING.md).
