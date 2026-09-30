# MikroTik RouterOS – verified sources and URL structure

**English** · [Čeština](ENDPOINTS.md)

Verified on: **2026-09-26**. Every claim below was verified with real HTTP requests
(`curl` + `tools/recon.py`), not taken from documentation. Where reality differs
from the original assumptions, it is marked explicitly as **⚠ DIFFERENCE**.

Reference versions used during the survey: **7.24.4** (stable/testing), **7.23.7**
(long-term), **7.25beta5** (development), **6.49.22** (v6 stable/long-term),
**7.13.5** (an older v7).

---

## 1. Hosts

| Host | Behaviour |
|---|---|
| `https://download.mikrotik.com` | primary, everything works |
| `https://upgrade.mikrotik.com` | identical content (`NEWEST*` and files), usable as a mirror |
| `https://cdn.mikrotik.com` | also works for `/routeros/<version>/<file>` |

Properties (verified on both `.npk` and `.zip`):

- `Accept-Ranges: bytes` → **Range requests and resuming work** (verified, `206 Partial Content`).
- `Content-Length`, `Last-Modified`, `ETag` (MD5-like) are present.
- **No redirects** (`num_redirects=0`), no CDN redirect loop.
- The server **does not require a particular User-Agent** — an empty UA and a custom
  UA both went through. (We still send our own `RosDownloader/<version>`.)
- Plain HTTP works too, but we use HTTPS exclusively.
- Directory listing is **not** available: `/routeros/` → `403`,
  `/routeros/<version>/` → `404`.

---

## 2. The newest version in a channel

```
https://upgrade.mikrotik.com/routeros/NEWESTa7.<channel>     # RouterOS v7
https://upgrade.mikrotik.com/routeros/NEWEST6.<channel>      # RouterOS v6
```

The response is a single line, `<version> <unix-timestamp>`, e.g.

```
7.24.4 1789558341        # 2026-09-16T11:32:21Z
```

Measured values:

| Channel | `NEWESTa7.*` | `NEWEST6.*` |
|---|---|---|
| `stable` | `7.24.4 1789558341` | `6.49.22 1789563951` |
| `long-term` | `7.23.7 1789561155` | `6.49.22 1789563951` |
| `testing` | `7.24.4 1789558341` | ⚠ returns `7.12.1` – **unusable** |
| `development` | `7.25beta5 1789557101` | ⚠ returns `7.12.1` – **unusable** |

**⚠ DIFFERENCES from the original assumptions:**

1. **`NEWEST7.<channel>` is stale and no longer updated** — it returns
   `7.12.1 1700221125` (November 2023) for `stable`/`testing`/`development`
   and `0.00` for `long-term`. For v7 we use **`NEWESTa7.<channel>` exclusively**.
   The same goes for `LATEST.7` (also `7.12.1`) and `LATEST.6` (`6.49.22`, current).
2. **v6 only has `stable` and `long-term`.** Both `NEWEST6.testing` and
   `NEWEST6.development` return `200` with the nonsensical content `7.12.1`
   (a leftover from v7). The GUI therefore offers only `stable` and `long-term` for v6.
3. `NEWESTa6.stable` exists and returns the same as `NEWEST6.stable` (an alias).
4. A non-existent channel returns an honest `404` (`NEWESTa7.bogus`), so it can be detected.

Consequence for the code: the check must be "the returned version has to start with
the expected major", otherwise the response is discarded (this guards against
`NEWEST6.testing` → `7.12.1`).

---

## 3. Architectures

The directory path is always `https://download.mikrotik.com/routeros/<version>/<file>`.

### v7 – the main package

```
routeros-<version>-<arch>.npk    # arm, arm64, mipsbe, mmips, smips, ppc, tile
routeros-<version>.npk           # x86 – WITHOUT the architecture suffix
```

Verified on 7.24.4 (all `200`) and on 7.25beta5 (all 8 `200`):

| arch | file (7.24.4) | size |
|---|---|---|
| x86 | `routeros-7.24.4.npk` | 20 837 260 |
| arm | `routeros-7.24.4-arm.npk` | 12 295 830 |
| arm64 | `routeros-7.24.4-arm64.npk` | 13 934 949 |
| mipsbe | `routeros-7.24.4-mipsbe.npk` | 11 448 036 |
| mmips | `routeros-7.24.4-mmips.npk` | 10 725 431 |
| smips | `routeros-7.24.4-smips.npk` | 7 196 348 |
| ppc | `routeros-7.24.4-ppc.npk` | 22 104 005 |
| tile | `routeros-7.24.4-tile.npk` | 16 927 105 |

`routeros-7.24.4-x86.npk` → **404** (a confirmed assumption).
These do not exist: `mips`, `mipsle`, `powerpc`, `e500`, `x86_64`, `amd64`, `arm7`,
`armv7`, `riscv`, `riscv64` (all 404). **The list of 8 v7 architectures is complete.**
`ppc` and `tile` are still built for 7.25beta5 as well — they have not been discontinued.

### v6 – the main package

```
routeros-<arch>-<version>.npk
```

**⚠ DIFFERENCES from the original assumptions:**

1. **x86 in v6 DOES have the suffix**: `routeros-x86-6.49.22.npk` → `200`,
   while `routeros-6.49.22.npk` → **404**. The "x86 without a suffix" rule applies
   in v6 **only to extra packages**, not to the main package.
2. **PowerPC is called `powerpc` in v6, not `ppc`**:
   `routeros-powerpc-6.49.22.npk` → `200` (17 955 262 B),
   `routeros-ppc-6.49.22.npk` → `404`.
   The archive and the extra packages nevertheless use `ppc`
   (`all_packages-ppc-6.49.22.zip`, `system-6.49.22-ppc.npk`). The code therefore
   needs a **separate "arch token" for the main package and for extras on v6/ppc**.
3. `mipsle` does not exist in v6 6.49.22 (404) — it was discontinued earlier.

Verified v6 main packages (6.49.22): `x86`, `arm`, `arm64`, `mipsbe`, `mmips`,
`smips`, `tile`, `powerpc`. So also 8, just with PowerPC named differently.

---

## 4. Extra packages

```
<package>-<version>-<arch>.npk   # v7 and v6, except x86
<package>-<version>.npk          # x86 – without the architecture suffix (v7 and v6)
```

Verified: `container-7.24.4-arm64.npk` `200`, `container-7.24.4.npk` `200`,
`container-7.24.4-x86.npk` **404**, `advanced-tools-6.49.22.npk` `200`,
`wireless-6.49.22-arm.npk` `200`.

Extra packages sit in the **same directory** as the main package and are available
individually too (there is no need to pull the whole ZIP).

### The package set is not fixed — it varies by version and architecture

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

This is why the list **must not be hardcoded** — it has to be read dynamically (see §5).

The full 7.24.4/arm64 list: `calea, container, dude, extra-nic, gps, iot,
iot-bt-extra, netinstall, openflow, rose-storage, switch-marvell, tr069-client,
ups, user-manager, wifi-qcom, wifi-qcom-be, wireless, zerotier`.

### v6: the archive holds a split-up system, not extras for "routeros"

The v6 archive contains, among others, `system-6.49.22-<arch>.npk`, `dhcp`, `ppp`,
`routing`, `security`, `ipv6`, `mpls`, `multicast`, `advanced-tools`, `ntp`,
`hotspot`, `wireless`, … Those are **components of a split system**, whereas
`routeros-<arch>-<version>.npk` is the merged bundle of them. The GUI mentions this
in a tooltip; otherwise it behaves the same.

Note: `routeros-ppc-6.49.22.npk` does not exist (nor in 6.48.6 / 6.45.9), but
`all_packages-ppc-6.49.22.zip` with `system-6.49.22-ppc.npk` does — for PowerPC on
v6 the only route is `routeros-powerpc-<version>.npk` (see above).

---

## 5. The all-packages archive and reading its index over HTTP Range

```
all_packages-<arch>-<version>.zip
```

Applies to **both v7 and v6** and to every architecture (7.24.4: all 8 `200`).
For v7/x86 it is `all_packages-x86-7.24.4.zip` — here `x86` **is** used in the ZIP
name, even though the files inside carry no suffix.

Other name variants are 404: `all_packages-<version>-<arch>.zip`,
`extra-packages-…`, `routeros-<version>-<arch>.zip`.

### Reading the Central Directory over Range – it works

The procedure was verified on `all_packages-arm64-7.24.4.zip` (50 582 938 B):

1. `HEAD` → `Content-Length`, `Accept-Ranges: bytes`.
2. `GET` with `Range: bytes=<size-65536>-` → `206`, the last 64 KiB.
3. Find the last `PK\x05\x06` (EOCD) in the buffer → entry count, `cd_size`, `cd_offset`.
   In the archives tested the comment was empty and the EOCD sat 22 B from the end;
   ZIP64 did not occur (but the code also checks for the `PK\x06\x07` locator).
4. If the whole Central Directory lies within the tail already fetched, it is read
   from there; otherwise a second `Range` request for `cd_offset … cd_offset+cd_size-1`.
5. Parse the `PK\x01\x02` records (46 B header + name + extra + comment).

Results: 18/18 entries for arm64, 12/12 x86, 3/3 smips, 9/9 ppc, 21/21 v6 arm,
23/23 v6 x86, 14/14 for 7.13.5 arm. About 66 KiB transferred in total instead of 50 MB.

**⚠ Mind the compression:** newer archives (7.24.4, 6.49.22) are **STORED**
(`method=0`, `csize == usize`), but **older archives are DEFLATE** (7.13.5 →
`method=8`, `csize != usize`). To display the size and to check it against the
`Content-Length` of a standalone `.npk`, you must use **`usize` (the uncompressed
size)**, never `csize`. Verified: `wifi-qcom-7.13.5-arm.npk` has `usize=7917713`,
`csize=7913709`.

The fallback method (a candidate list plus parallel HEADs) stays implemented, but is
only used when the ZIP is missing or its CD cannot be read.

---

## 6. Changelog

```
https://upgrade.mikrotik.com/routeros/<version>/CHANGELOG
https://download.mikrotik.com/routeros/<version>/CHANGELOG      # same content
```

Plain text, `200` for an existing version, `404` otherwise. Example (7.24.4, 579 B):

```
What's new in 7.24.4 (2026-09-16):

*) lte - prevent the modem firmware from being deleted for RBSXTLTE3-7, …
```

It exists for v6 too (`6.49.22`, 93 B) and for betas/rcs (`7.25beta5`, `7.24rc1`).

---

## 7. Version history

**⚠ DIFFERENCE – the `mikrotik.com/download` page cannot be parsed.**
The page (and `/download/archive`, which returns the same content) is built on
**Livewire + Alpine.js** and fetches the version list only via an AJAX call to
`/livewire/update`. The downloaded HTML contains not a single occurrence of `7.24`,
`routeros-…npk` or `long-term`. Without a headless browser (which the brief forbids)
this route is a dead end. The `/download/changelogs` page is partially server-rendered
and contains the last ~20 versions in `x-on:header-click="toggleChangelog('7.23.7')"`
attributes, but that is fragile and incomplete.

**The chosen solution: enumeration via `CHANGELOG` (HEAD).** It is deterministic,
independent of the HTML, and returns exactly those versions that are really downloadable.

Verified range (HEAD on `…/<version>/CHANGELOG`, `200` = exists):

- **v7 minor:** `7.1` – `7.24` (all exist, no gaps)
- **v7 patch:** 7.1.1–7.1.5, 7.2.1–7.2.3, 7.3.1, 7.4.1, 7.9.1–7.9.2, 7.10.1–7.10.2,
  7.11.1–7.11.3, 7.12.1–7.12.2, 7.13.1–7.13.5, 7.14.1–7.14.3, 7.15.1–7.15.3,
  7.16.1–7.16.2, 7.17.1–7.17.2, 7.18.1–7.18.2, 7.19.1–7.19.6, 7.20.1–7.20.8,
  7.21.1–7.21.5, 7.22.1–7.22.3, 7.23.1–7.23.7, 7.24.1–7.24.4
  (7.5–7.8 have no patches)
- **v6 minor:** `6.0` – `6.49` except `6.8` and `6.31` (those return 404)
- **v6 patch:** 6.49.1 – 6.49.22
- **beta/rc:** `7.25beta3`, `7.25beta4`, `7.25beta5`, `7.24beta1`, `7.24rc1`, `7.23rc1`
  → the form is `<major>.<minor>beta<N>` / `<major>.<minor>rc<N>`, **with no separator**,
  and the files in that directory are named the same way (`routeros-7.25beta5-arm64.npk`
  `200`, `all_packages-arm64-7.25beta5.zip` `200`).

The strategy in the app (so that startup is not ~300 requests):

1. At startup only `NEWESTa7.stable` — that is all the default state needs.
2. The history loads **in the background and lazily**, descending from the newest
   minor: for each minor try `x.y`, then `x.y.1, x.y.2, …` until two misses in a row;
   try minors down to `.1`. At most 8 concurrent HEADs.
3. **Cache** the result in `%APPDATA%\RosDownloader\versions.json` with a TTL
   (e.g. 24 h; the newest version from `NEWEST*` is always checked).
4. The user can type a version at any time — the entered version is verified with a
   single HEAD on `CHANGELOG`.

---

## 8. SHA256 – **it is available**

**⚠ Better than the brief assumed.** **Every** file has a sidecar:

```
https://download.mikrotik.com/routeros/<version>/<file>.sha256
```

The format is the standard `sha256sum` one (64 hex + two spaces + the file name,
~86–96 B):

```
627b9a58820b3b7a754992e1330341ffb61f8e61aa72e186bcbc2c55ebc06793  routeros-7.24.4-arm64.npk
```

Verified for: v7 main (both with the suffix and x86 without it), v7 extras,
`all_packages*.zip`, v6 main and the v6 ZIP, and on `upgrade.mikrotik.com`.
**The sidecar matches reality** — `calea-7.24.4-arm64.npk` (20 625 B) was downloaded
and the computed SHA256
`394442ef38c5e09cb15f77527951179a810a40f8b20e074721613f221a713e2b` matches the sidecar.

Aggregate files do not exist: `CHECKSUM`, `CHECKSUMS`, `SHA256SUMS`,
`sha256sums.txt`, `checksums.txt`, `MD5SUMS` → all 404. An `.md5` sidecar is 404 too.

Consequence: **always verify SHA256** (one extra small GET per file), and only when
the sidecar is missing (404) fall back to checking the size against `Content-Length`
or against `usize` from the ZIP Central Directory.

---

## 9. Error behaviour

- A non-existent package / architecture / version → a clean **`404`** with an empty
  body. The GUI maps this to "the package does not exist for that version or
  architecture".
- `/routeros/` → `403`, `/routeros/<version>/` → `404` (no directory listing).
- With 12 concurrent HEAD requests no rate limiting appeared.

---

## 10. Summary of the URL rules

```
BASE = https://download.mikrotik.com/routeros/<version>

v7  main   : routeros-<version>-<arch>.npk      | x86: routeros-<version>.npk
v7  extra  : <pkg>-<version>-<arch>.npk         | x86: <pkg>-<version>.npk
v6  main   : routeros-<arch6>-<version>.npk     | x86 ALSO with the suffix
             where arch6: ppc -> powerpc, otherwise unchanged
v6  extra  : <pkg>-<version>-<arch>.npk         | x86: <pkg>-<version>.npk
both zip   : all_packages-<arch>-<version>.zip  | x86 with the suffix, without it inside
both sha256: <any file listed above>.sha256
changelog  : CHANGELOG
newest     : https://upgrade.mikrotik.com/routeros/NEWESTa7.<channel>  (v7)
             https://upgrade.mikrotik.com/routeros/NEWEST6.<channel>   (v6, stable/long-term only)
```

Three places where it is easy to get it wrong, and which therefore have tests:
`x86` without a suffix in v7 main, `x86` **with** a suffix in v6 main,
and `ppc`→`powerpc` in v6 main only.
