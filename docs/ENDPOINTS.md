# MikroTik RouterOS – ověřené zdroje a struktura URL

Stav ověření: **2026-09-26**. Všechna tvrzení níže jsou ověřená skutečnými HTTP dotazy
(`curl` + `tools/recon.py`), ne převzatá z dokumentace. Kde se realita liší od původních
předpokladů v zadání, je to výslovně označeno **⚠ ODLIŠNOST**.

Referenční verze použité při průzkumu: **7.24.4** (stable/testing), **7.23.7** (long-term),
**7.25beta5** (development), **6.49.22** (v6 stable/long-term), **7.13.5** (starší v7).

---

## 1. Hosty

| Host | Chování |
|---|---|
| `https://download.mikrotik.com` | primární, vše funguje |
| `https://upgrade.mikrotik.com` | totožný obsah (`NEWEST*` i soubory), lze použít jako mirror |
| `https://cdn.mikrotik.com` | také funguje pro `/routeros/<verze>/<soubor>` |

Vlastnosti (ověřeno na `.npk` i `.zip`):

- `Accept-Ranges: bytes` → **Range požadavky a resume fungují** (ověřeno `206 Partial Content`).
- `Content-Length`, `Last-Modified`, `ETag` (MD5-like) jsou přítomny.
- **Žádné přesměrování** (`num_redirects=0`), žádná CDN redirect smyčka.
- Server **nevyžaduje konkrétní User-Agent** – prošel i prázdný UA i vlastní UA.
  (Přesto nastavíme vlastní `RosDownloader/<verze>`.)
- Funguje i čisté HTTP, ale používáme výhradně HTTPS.
- Výpis adresáře **není** k dispozici: `/routeros/` → `403`, `/routeros/<verze>/` → `404`.

---

## 2. Nejnovější verze v kanálu

```
https://upgrade.mikrotik.com/routeros/NEWESTa7.<kanál>     # RouterOS v7
https://upgrade.mikrotik.com/routeros/NEWEST6.<kanál>      # RouterOS v6
```

Odpověď je jeden řádek: `<verze> <unix-timestamp>`, např.

```
7.24.4 1789558341        # 2026-09-16T11:32:21Z
```

Naměřené hodnoty:

| Kanál | `NEWESTa7.*` | `NEWEST6.*` |
|---|---|---|
| `stable` | `7.24.4 1789558341` | `6.49.22 1789563951` |
| `long-term` | `7.23.7 1789561155` | `6.49.22 1789563951` |
| `testing` | `7.24.4 1789558341` | ⚠ vrací `7.12.1` – **nepoužitelné** |
| `development` | `7.25beta5 1789557101` | ⚠ vrací `7.12.1` – **nepoužitelné** |

**⚠ ODLIŠNOSTI proti zadání:**

1. **`NEWEST7.<kanál>` je zastaralý a neaktualizuje se** – vrací `7.12.1 1700221125`
   (listopad 2023) pro `stable`/`testing`/`development` a `0.00` pro `long-term`.
   Pro v7 se používá **výhradně `NEWESTa7.<kanál>`**. Totéž platí pro `LATEST.7`
   (také `7.12.1`) a `LATEST.6` (`6.49.22`, aktuální).
2. **v6 má jen `stable` a `long-term`.** `NEWEST6.testing` i `NEWEST6.development`
   vracejí `200` s nesmyslným obsahem `7.12.1` (zbytek po v7). V GUI proto pro v6
   nabídneme pouze `stable` a `long-term`.
3. `NEWESTa6.stable` existuje a vrací totéž co `NEWEST6.stable` (alias).
4. Neexistující kanál vrací poctivou `404` (`NEWESTa7.bogus`), takže se dá detekovat.

Důsledek pro kód: kontrola musí být „vrácená verze musí začínat očekávaným majorem“,
jinak se odpověď zahodí (chrání před `NEWEST6.testing` → `7.12.1`).

---

## 3. Architektury

Adresářová cesta je vždy `https://download.mikrotik.com/routeros/<verze>/<soubor>`.

### v7 – hlavní balíček

```
routeros-<verze>-<arch>.npk      # arm, arm64, mipsbe, mmips, smips, ppc, tile
routeros-<verze>.npk             # x86 – BEZ přípony architektury
```

Ověřeno na 7.24.4 (všechny `200`) i 7.25beta5 (všech 8 `200`):

| arch | soubor (7.24.4) | velikost |
|---|---|---|
| x86 | `routeros-7.24.4.npk` | 20 837 260 |
| arm | `routeros-7.24.4-arm.npk` | 12 295 830 |
| arm64 | `routeros-7.24.4-arm64.npk` | 13 934 949 |
| mipsbe | `routeros-7.24.4-mipsbe.npk` | 11 448 036 |
| mmips | `routeros-7.24.4-mmips.npk` | 10 725 431 |
| smips | `routeros-7.24.4-smips.npk` | 7 196 348 |
| ppc | `routeros-7.24.4-ppc.npk` | 22 104 005 |
| tile | `routeros-7.24.4-tile.npk` | 16 927 105 |

`routeros-7.24.4-x86.npk` → **404** (potvrzený předpoklad ze zadání).
Neexistují: `mips`, `mipsle`, `powerpc`, `e500`, `x86_64`, `amd64`, `arm7`, `armv7`,
`riscv`, `riscv64` (vše 404). **Seznam 8 architektur v7 je úplný.**
`ppc` a `tile` se stále sestavují i pro 7.25beta5 – nejsou ukončené.

### v6 – hlavní balíček

```
routeros-<arch>-<verze>.npk
```

**⚠ ODLIŠNOSTI proti zadání:**

1. **x86 ve v6 příponu MÁ**: `routeros-x86-6.49.22.npk` → `200`,
   zatímco `routeros-6.49.22.npk` → **404**. Pravidlo „x86 bez přípony“ platí
   ve v6 **jen pro extra balíčky**, ne pro hlavní balíček.
2. **PowerPC se ve v6 jmenuje `powerpc`, ne `ppc`**:
   `routeros-powerpc-6.49.22.npk` → `200` (17 955 262 B),
   `routeros-ppc-6.49.22.npk` → `404`.
   Přitom archiv i extra balíčky používají `ppc` (`all_packages-ppc-6.49.22.zip`,
   `system-6.49.22-ppc.npk`). V kódu je tedy potřeba **oddělený „arch token“
   pro hlavní balíček a pro extras u v6/ppc**.
3. `mipsle` ve v6 6.49.22 neexistuje (404) – byl ukončen dříve.

Ověřené v6 hlavní balíčky (6.49.22): `x86`, `arm`, `arm64`, `mipsbe`, `mmips`,
`smips`, `tile`, `powerpc`. Tedy také 8, jen s jiným pojmenováním PowerPC.

---

## 4. Extra balíčky

```
<balíček>-<verze>-<arch>.npk      # v7 i v6, mimo x86
<balíček>-<verze>.npk             # x86 – bez přípony architektury (v7 i v6)
```

Ověřeno: `container-7.24.4-arm64.npk` `200`, `container-7.24.4.npk` `200`,
`container-7.24.4-x86.npk` **404**, `advanced-tools-6.49.22.npk` `200`,
`wireless-6.49.22-arm.npk` `200`.

Extra balíčky leží ve **stejném adresáři** jako hlavní balíček a jsou dostupné
i jednotlivě (nemusí se tahat celý ZIP).

### Sada balíčků není pevná – liší se podle verze i architektury

| | 7.24.4 arm64 (18) | 7.24.4 x86 (12) | 7.24.4 smips (3) | 7.13.5 arm (14) |
|---|---|---|---|---|
| container | ✓ | ✓ | – | ✓ |
| wifi-qcom | ✓ | – | – | ✓ |
| wifi-qcom-be | ✓ | – | – | – |
| wifi-qcom-ac | – | – | – | ✓ |
| switch-marvell | ✓ | – | – | – |
| extra-nic | ✓ | – | – | – |
| iot-bt-extra | ✓ | – | – | – |
| zerotier | ✓ | – | – | ✓ |
| lora | – | – | – | ✓ |
| hotspot | – | – | ✓ | – |
| rose-storage | ✓ | ✓ | – | ✓ |

Proto **nesmí být seznam natvrdo v kódu** – musí se číst dynamicky (viz §5).

Plný seznam 7.24.4/arm64: `calea, container, dude, extra-nic, gps, iot,
iot-bt-extra, netinstall, openflow, rose-storage, switch-marvell, tr069-client,
ups, user-manager, wifi-qcom, wifi-qcom-be, wireless, zerotier`.

### v6: archiv obsahuje rozpadlý systém, ne extras k „routeros“

V6 archiv obsahuje mj. `system-6.49.22-<arch>.npk`, `dhcp`, `ppp`, `routing`,
`security`, `ipv6`, `mpls`, `multicast`, `advanced-tools`, `ntp`, `hotspot`, `wireless`, …
To jsou **komponenty rozděleného systému**, zatímco `routeros-<arch>-<verze>.npk`
je jejich sloučený balík. V GUI to zmíníme v tooltipu, jinak se chová stejně.

Pozn.: `routeros-ppc-6.49.22.npk` neexistuje (ani v 6.48.6 / 6.45.9), ale
`all_packages-ppc-6.49.22.zip` se `system-6.49.22-ppc.npk` ano – pro PowerPC
je ve v6 jediná cesta `routeros-powerpc-<verze>.npk` (viz výše).

---

## 5. Archiv všech balíčků a čtení seznamu přes HTTP Range

```
all_packages-<arch>-<verze>.zip
```

Platí pro **v7 i v6** a pro všechny architektury (7.24.4: všech 8 `200`).
Pro v7/x86 je to `all_packages-x86-7.24.4.zip` – zde se `x86` v názvu ZIPu
**používá**, i když soubory uvnitř příponu nemají.

Jiné varianty názvu jsou 404: `all_packages-<verze>-<arch>.zip`,
`extra-packages-…`, `routeros-<verze>-<arch>.zip`.

### Range čtení Central Directory – funguje

Postup ověřen na `all_packages-arm64-7.24.4.zip` (50 582 938 B):

1. `HEAD` → `Content-Length`, `Accept-Ranges: bytes`.
2. `GET` s `Range: bytes=<size-65536>-` → `206`, posledních 64 KiB.
3. V bufferu najít poslední `PK\x05\x06` (EOCD) → počet záznamů, `cd_size`, `cd_offset`.
   U testovaných archivů byl komentář prázdný a EOCD 22 B od konce; ZIP64 se nevyskytl
   (ale kód kontroluje i lokátor `PK\x06\x07`).
4. Pokud Central Directory leží celá v načteném ocasu, čte se z něj; jinak druhý
   `Range` požadavek na `cd_offset … cd_offset+cd_size-1`.
5. Parsovat `PK\x01\x02` záznamy (46 B hlavička + název + extra + komentář).

Výsledky: 18/18 záznamů pro arm64, 12/12 x86, 3/3 smips, 9/9 ppc, 21/21 v6 arm,
23/23 v6 x86, 14/14 pro 7.13.5 arm. Celkem ~66 KiB přenesených dat místo 50 MB.

**⚠ Pozor na kompresi:** novější archivy (7.24.4, 6.49.22) jsou **STORED**
(`method=0`, `csize == usize`), ale **starší archivy jsou DEFLATE** (7.13.5 →
`method=8`, `csize != usize`). Pro zobrazení velikosti a pro kontrolu proti
`Content-Length` samostatného `.npk` se musí použít **`usize` (nekomprimovaná
velikost)**, nikdy `csize`. Ověřeno: `wifi-qcom-7.13.5-arm.npk` má `usize=7917713`,
`csize=7913709`.

Záložní metoda (kandidátní seznam + paralelní HEAD) zůstane implementovaná,
ale použije se jen když ZIP chybí nebo je CD nečitelná.

---

## 6. Changelog

```
https://upgrade.mikrotik.com/routeros/<verze>/CHANGELOG
https://download.mikrotik.com/routeros/<verze>/CHANGELOG      # stejný obsah
```

Prostý text, `200` pro existující verzi, `404` jinak. Příklad (7.24.4, 579 B):

```
What's new in 7.24.4 (2026-09-16):

*) lte - prevent the modem firmware from being deleted for RBSXTLTE3-7, …
```

Existuje i pro v6 (`6.49.22`, 93 B) a pro beta/rc (`7.25beta5`, `7.24rc1`).

---

## 7. Historie verzí

**⚠ ODLIŠNOST – stránku `mikrotik.com/download` nelze parsovat.**
Stránka (i `/download/archive`, což vrací stejný obsah) je postavená na **Livewire +
Alpine.js** a seznam verzí dotahuje až AJAX voláním na `/livewire/update`.
Ve staženém HTML není ani jeden řetězec `7.24`, `routeros-…npk` ani `long-term`.
Bez headless prohlížeče (zadání ho zakazuje) je tato cesta slepá.
Stránka `/download/changelogs` je částečně server-rendered a obsahuje posledních
~20 verzí v atributech `x-on:header-click="toggleChangelog('7.23.7')"`, ale
je to křehké a neúplné.

**Zvolené řešení: enumerace přes `CHANGELOG` (HEAD).** Je deterministická,
nezávislá na HTML a vrací přesně ty verze, které jsou reálně ke stažení.

Ověřený rozsah (HEAD na `…/<verze>/CHANGELOG`, `200` = existuje):

- **v7 minor:** `7.1` – `7.24` (všechny existují, bez mezer)
- **v7 patch:** 7.1.1–7.1.5, 7.2.1–7.2.3, 7.3.1, 7.4.1, 7.9.1–7.9.2, 7.10.1–7.10.2,
  7.11.1–7.11.3, 7.12.1–7.12.2, 7.13.1–7.13.5, 7.14.1–7.14.3, 7.15.1–7.15.3,
  7.16.1–7.16.2, 7.17.1–7.17.2, 7.18.1–7.18.2, 7.19.1–7.19.6, 7.20.1–7.20.8,
  7.21.1–7.21.5, 7.22.1–7.22.3, 7.23.1–7.23.7, 7.24.1–7.24.4
  (7.5–7.8 patche nemají)
- **v6 minor:** `6.0` – `6.49` kromě `6.8` a `6.31` (ty vracejí 404)
- **v6 patch:** 6.49.1 – 6.49.22
- **beta/rc:** `7.25beta3`, `7.25beta4`, `7.25beta5`, `7.24beta1`, `7.24rc1`, `7.23rc1`
  → tvar je `<major>.<minor>beta<N>` / `<major>.<minor>rc<N>`, **bez oddělovače**,
  a soubory v tom adresáři se jmenují stejně (`routeros-7.25beta5-arm64.npk` `200`,
  `all_packages-arm64-7.25beta5.zip` `200`).

Strategie v aplikaci (aby to nebylo ~300 requestů při startu):

1. Při startu jen `NEWESTa7.stable` – to je jediné, co je potřeba pro výchozí stav.
2. Historie se načítá **na pozadí a líně**, sestupně od nejnovější minor verze:
   pro každou minor zkoušet `x.y`, pak `x.y.1, x.y.2, …` dokud nepřijdou 2 miss v řadě;
   minor verze zkoušet dolů do `.1`. Max 8 souběžných HEAD.
3. Výsledek **cachovat** do `%APPDATA%\RosDownloader\versions.json` s TTL
   (např. 24 h; nejnovější verze z `NEWEST*` se kontroluje vždy).
4. Uživatel může verzi kdykoli napsat ručně – zadaná verze se ověří jedním HEAD
   na `CHANGELOG`.

---

## 8. SHA256 – **je k dispozici**

**⚠ Lepší, než zadání předpokládalo.** Ke **každému** souboru existuje sidecar:

```
https://download.mikrotik.com/routeros/<verze>/<soubor>.sha256
```

Formát je standardní `sha256sum` (64 hex + dvě mezery + název souboru, ~86–96 B):

```
627b9a58820b3b7a754992e1330341ffb61f8e61aa72e186bcbc2c55ebc06793  routeros-7.24.4-arm64.npk
```

Ověřeno pro: hlavní v7 (s příponou i x86 bez ní), extra v7, `all_packages*.zip`,
hlavní v6 i v6 ZIP, a na `upgrade.mikrotik.com`. **Sidecar se shoduje se skutečností** –
staženo `calea-7.24.4-arm64.npk` (20 625 B) a spočtený SHA256
`394442ef38c5e09cb15f77527951179a810a40f8b20e074721613f221a713e2b` odpovídá sidecaru.

Agregátní soubory neexistují: `CHECKSUM`, `CHECKSUMS`, `SHA256SUMS`,
`sha256sums.txt`, `checksums.txt`, `MD5SUMS` → vše 404. `.md5` sidecar také 404.

Důsledek: ověřovat **vždy SHA256** (jeden malý GET navíc na soubor), a jen když
sidecar chybí (404), spadnout na kontrolu velikosti proti `Content-Length` /
`usize` ze ZIP Central Directory.

---

## 9. Chování při chybách

- Neexistující balíček / architektura / verze → čistá **`404`** s prázdným tělem.
  V GUI se mapuje na hlášku „balíček pro danou verzi nebo architekturu neexistuje“.
- `/routeros/` → `403`, `/routeros/<verze>/` → `404` (žádný výpis adresáře).
- Při 12 souběžných HEAD požadavcích se neprojevil žádný rate-limit.

---

## 10. Shrnutí pravidel pro sestavení URL

```
BASE = https://download.mikrotik.com/routeros/<verze>

v7  main   : routeros-<verze>-<arch>.npk        | x86: routeros-<verze>.npk
v7  extra  : <pkg>-<verze>-<arch>.npk           | x86: <pkg>-<verze>.npk
v6  main   : routeros-<arch6>-<verze>.npk       | x86 TAKÉ s příponou
             kde arch6: ppc -> powerpc, jinak stejné
v6  extra  : <pkg>-<verze>-<arch>.npk           | x86: <pkg>-<verze>.npk
oba zip    : all_packages-<arch>-<verze>.zip    | x86 s příponou, uvnitř bez ní
oba sha256 : <libovolný výše uvedený soubor>.sha256
changelog  : CHANGELOG
newest     : https://upgrade.mikrotik.com/routeros/NEWESTa7.<kanál>   (v7)
             https://upgrade.mikrotik.com/routeros/NEWEST6.<kanál>    (v6, jen stable/long-term)
```

Tři místa, kde se dá chybovat, a proto k nim budou testy:
`x86` bez přípony ve v7 main, `x86` **s** příponou ve v6 main,
a `ppc`→`powerpc` jen ve v6 main.
