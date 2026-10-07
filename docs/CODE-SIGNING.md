# Podepisování kódu

[English](CODE-SIGNING.en.md) · **Čeština**

Tenhle dokument je zároveň **code signing policy** projektu – SignPath
Foundation ji po podepisovaných projektech vyžaduje – a návod, jak je
podepisování nastavené.

## Proč

`RosDownloader.exe` je nepodepsaný soubor stažený z internetu. Windows mu
přes Mark-of-the-Web pozná původ a SmartScreen ho zablokuje hlášením
„Windows chrání váš počítač“, protože k podpisu ani k reputaci souboru nemá
co přiřadit. Nejde to obejít ničím jiným než **platným podpisem Authenticode
od certifikační autority, které Windows věří** – podpis vlastním
(self-signed) certifikátem s tím neudělá nic, SmartScreen takový podpis
ignoruje.

Certifikáty se nedají dát do repozitáře ani do rukou buildu na notebooku, a
komerční certifikát stojí stovky dolarů ročně. Proto projekt používá
**[SignPath Foundation](https://signpath.org/)**, která certifikáty pro
open-source projekty poskytuje zdarma, a podepisuje jen binárky, o kterých
si sama ověří, že vznikly z veřejných zdrojáků.

## Jak je to zařízené

Podepsaný `.exe` vzniká **výhradně** v
[`.github/workflows/release.yml`](../.github/workflows/release.yml) na
runneru GitHubu:

1. Workflow se spustí na tagu `v*`.
2. Zkontroluje, že tag odpovídá `rosdl.__version__`.
3. Sestaví `.exe` tím samým `build.ps1`, kterým se staví lokálně.
4. Nahraje nepodepsaný `.exe` jako artefakt běhu.
5. Pošle ho SignPathu k podpisu a počká na výsledek.
6. Ověří podpis přes `Get-AuthenticodeSignature` – nevalidní podpis build shodí.
7. Přiloží podepsaný `.exe` k releasu (nebo založí koncept, popis vydání se
   píše ručně).

SignPath si přitom sám u GitHubu ověří, z jakého repozitáře, commitu a běhu
artefakt pochází (*origin verification*). Vlastnost, která z toho plyne a
na kterou je dobré nezapomenout:

> **Ručně sestavený `.exe` nahraný k releasu zůstane nepodepsaný.**
> Vydávat se dá jedině tagem, který projde workflow.

Lokální `build.ps1` proto podpis vůbec neřeší a na konci to řekne nahlas.

### Co se podepisuje

Jedině `RosDownloader.exe` sestavený ze zdrojáků tohohle repozitáře, z větve
`main`, tagované verze. Nic jiného: žádné instalátory, žádné skripty,
žádné binárky třetích stran.

### Kdo smí podpis vyvolat

Podpis může vyvolat jen běh workflow z tohohle repozitáře. Lidsky jen ten,
kdo může do repozitáře zatlačit tag `v*`, tedy vlastník repozitáře
(johnnybee05). API token SignPathu je uložený jako secret GitHubu a nikde se
nevypisuje.

### Jak si podpis ověřit

```powershell
Get-AuthenticodeSignature .\RosDownloader.exe | Format-List
```

`Status` musí být `Valid` a v `SignerCertificate` musí být jako subjekt
**SignPath Foundation** – ta je u certifikátů z jejich programu uvedená jako
vydavatel, ne autor projektu. Vedle toho u každého vydání zůstává SHA256:

```powershell
Get-FileHash .\RosDownloader.exe -Algorithm SHA256
```

### Když je něco špatně

Podezření na zneužití certifikátu nebo na podepsanou binárku, která
nepochází odsud, patří do
[issues](https://github.com/johnnybee05/RouterOS_Download_App/issues)
a současně na [SignPath](https://signpath.io/support) – ta certifikát
v takovém případě odvolá.

## Nastavení (jednorázově)

Workflow je napsaný tak, že **dokud SignPath nastavený není, krok s podpisem
se přeskočí** a vydá se nepodepsaný `.exe` s varováním v logu. Zapne se
doplněním proměnných níž.

### 1. Přihlásit projekt

Žádost se podává na <https://signpath.org/apply>. Podmínky, které projekt
plní: OSI licence (MIT), veřejný repozitář, plně automatizovaný build na
GitHub Actions, popis aplikace na stránce ke stažení, žádné proprietární
součásti. Schválení trvá řádově dny.

### 2. Artifact configuration

`actions/upload-artifact` zabalí `.exe` do ZIPu, takže konfigurace na straně
SignPathu musí počítat se ZIPem, ve kterém je jeden PE soubor:

```xml
<?xml version="1.0" encoding="utf-8"?>
<artifact-configuration xmlns="http://signpath.io/artifact-configuration/v1">
  <zip-file>
    <pe-file path="RosDownloader.exe">
      <authenticode-sign />
    </pe-file>
  </zip-file>
</artifact-configuration>
```

### 3. Proměnné a secret v repozitáři

*Settings → Secrets and variables → Actions*:

| Jméno                                   | Druh     | Odkud                             |
| --------------------------------------- | -------- | --------------------------------- |
| `SIGNPATH_API_TOKEN`                    | secret   | SignPath → User → API tokens      |
| `SIGNPATH_ORGANIZATION_ID`              | variable | SignPath → Organization → ID      |
| `SIGNPATH_PROJECT_SLUG`                 | variable | slug projektu, např. `rosdownloader` |
| `SIGNPATH_SIGNING_POLICY_SLUG`          | variable | `release-signing`                 |
| `SIGNPATH_ARTIFACT_CONFIGURATION_SLUG`  | variable | slug konfigurace z kroku 2        |

`SIGNPATH_ORGANIZATION_ID` je ta proměnná, podle které se krok s podpisem
zapíná – bez ní se přeskočí.

### 4. Vyzkoušet nanečisto

Workflow se dá spustit ručně (*Actions → release → Run workflow*). Bez tagu
nic nevydá, jen nechá podepsaný `.exe` ke stažení jako artefakt běhu. Na
zkoušky je lepší mít v `SIGNPATH_SIGNING_POLICY_SLUG` dočasně
`test-signing` – testovací certifikát SmartScreen neuklidní, ale ověří, že
celá cesta funguje.

## Co s tím mezitím

Dokud podpis není, zbývá uživatelům *Více informací → Přesto spustit* a
ověření otisku. Dvě věci, které se k tomu dají udělat a projekt je dělá:

- **Metadata souboru.** `.exe` nese VERSIONINFO (výrobce, popis, verze,
  copyright) z [`tools/make_version_file.py`](../tools/make_version_file.py).
  Úplně prázdné vlastnosti souboru jsou pro heuristiky signál samy o sobě.
- **Žádné UPX.** `build.ps1` staví s `--noupx`, protože zabalené binárky
  hlásí jako podezřelé velká část antivirů. PyInstaller si UPX bere, jen když
  ho najde v `PATH`, takže to dřív záleželo na tom, kde se staví; teď se
  vypíná výslovně.

## Poděkování

Free code signing provided by [SignPath.io](https://signpath.io/),
certificate by [SignPath Foundation](https://signpath.org/).
