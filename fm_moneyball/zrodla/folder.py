"""
Folder zapisow FM26: domyslne lokalizacje, lista zapisow od najnowszego, bezpieczna kopia.

"Aktualnie zaladowany" zapis to w praktyce plik .fm zmodyfikowany najpozniej - gra zapisuje
go przy kazdym zapisie recznym i autozapisie. Gra nie udostepnia innej, oficjalnej informacji
o tym, ktora kariera jest otwarta.
"""
import os
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

PODFOLDER_GRY = Path("Sports Interactive") / "Football Manager 26" / "games"
STEAM_APP_ID = "3551340"


@dataclass(frozen=True)
class PlikZapisu:
    sciezka: Path
    rozmiar: int
    mtime: float

    @property
    def nazwa(self):
        return self.sciezka.name


def kandydaci_folderow(home=None, platforma=None, srodowisko=None):
    """Mozliwe lokalizacje folderu 'games' (bez sprawdzania, czy istnieja)."""
    home = Path(home) if home else Path.home()
    platforma = platforma or sys.platform
    srodowisko = os.environ if srodowisko is None else srodowisko
    kandydaci = []
    if platforma.startswith("win"):
        profil = Path(srodowisko.get("USERPROFILE", home))
        onedrive = srodowisko.get("OneDrive") or srodowisko.get("OneDriveConsumer")
        if onedrive:
            kandydaci += [Path(onedrive) / "Documents" / PODFOLDER_GRY, Path(onedrive) / "Dokumenty" / PODFOLDER_GRY]
        kandydaci += [profil / "Documents" / PODFOLDER_GRY, profil / "Dokumenty" / PODFOLDER_GRY]
    elif platforma == "darwin":
        kandydaci.append(home / "Library" / "Application Support" / PODFOLDER_GRY)
    else:
        # Linux / Steam Deck (Proton)
        kompat = (home / ".local" / "share" / "Steam" / "steamapps" / "compatdata" / STEAM_APP_ID
                  / "pfx" / "drive_c" / "users" / "steamuser")
        kandydaci += [kompat / "Documents" / PODFOLDER_GRY, kompat / "My Documents" / PODFOLDER_GRY,
                      home / ".local" / "share" / PODFOLDER_GRY]
    return kandydaci


def domyslny_folder(**kwargs):
    """Pierwszy istniejacy folder zapisow albo None."""
    for kandydat in kandydaci_folderow(**kwargs):
        if kandydat.is_dir():
            return kandydat
    return None


def lista_zapisow(folder):
    """Pliki .fm w folderze (bez podfolderow), od najnowszego."""
    folder = Path(folder)
    if not folder.is_dir():
        return []
    pliki = []
    for sciezka in folder.glob("*.fm"):
        try:
            stat = sciezka.stat()
        except OSError:
            continue
        if sciezka.is_file():
            pliki.append(PlikZapisu(sciezka, stat.st_size, stat.st_mtime))
    return sorted(pliki, key=lambda p: p.mtime, reverse=True)


def najnowszy_zapis(folder):
    pliki = lista_zapisow(folder)
    return pliki[0] if pliki else None


def czy_stabilny(sciezka, odstep=1.0):
    """Czy plik nie jest wlasnie zapisywany przez gre (rozmiar i mtime bez zmian po `odstep` s)."""
    try:
        przed = os.stat(sciezka)
        time.sleep(odstep)
        po = os.stat(sciezka)
    except OSError:
        return False
    return (przed.st_size, przed.st_mtime) == (po.st_size, po.st_mtime)


def folder_kopii():
    folder = Path(tempfile.gettempdir()) / "fm_moneyball"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def bezpieczna_kopia(zapis, folder_docelowy=None, zachowaj=2):
    """
    Kopiuje zapis do folderu tymczasowego, zeby gra mogla go nadpisac w trakcie analizy.
    Kopia jest nazwana po czasie modyfikacji, wiec ten sam stan zapisu nie jest kopiowany
    drugi raz. Starsze kopie (poza `zachowaj` najnowszymi) sa usuwane.
    """
    folder_docelowy = Path(folder_docelowy) if folder_docelowy else folder_kopii()
    folder_docelowy.mkdir(parents=True, exist_ok=True)
    cel = folder_docelowy / f"{zapis.sciezka.stem}-{int(zapis.mtime)}-{zapis.rozmiar}.fm"
    if not cel.exists():
        tymczasowy = cel.with_suffix(".tmp")
        shutil.copyfile(zapis.sciezka, tymczasowy)
        os.replace(tymczasowy, cel)
    kopie = sorted(folder_docelowy.glob("*.fm"), key=lambda p: p.stat().st_mtime, reverse=True)
    for stara in kopie[zachowaj:]:
        if stara != cel:
            try:
                stara.unlink()
            except OSError:
                pass
    return cel
