# Specyfikacja PyInstallera: program FM26Moneyball (Windows) we wlasnym oknie, bez konsoli.
# Tryb "folder" (onedir): dist/FM26Moneyball/FM26Moneyball.exe + _internal/ - start bez rozpakowywania
# (szybciej niz jeden plik) i mniej falszywych alarmow antywirusa. Instalator buduje z tego folderu
# Inno Setup (instalator/fm26_moneyball.iss).
# Budowanie: pyinstaller fm26_moneyball.spec   (wynik w dist/FM26Moneyball/)
# Na GitHubie buduje go workflow .github/workflows/exe.yml.
import re
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

WERSJA = re.search(r'__version__ = "([^"]+)"', Path("fm_moneyball/__init__.py").read_text()).group(1)
CZESCI = tuple(int(x) for x in WERSJA.split(".")) + (0,)

datas = [
    ("fm_moneyball/serwer/static", "fm_moneyball/serwer/static"),   # zbudowany interfejs React
    ("dane/*.csv", "dane"),                                         # domyslne nazwy lig i krajow
]
datas += collect_data_files("fmsave")
datas += copy_metadata("fmsave")          # fmsave.__version__ czyta metadane pakietu

hiddenimports = (collect_submodules("fmsave") + collect_submodules("uvicorn")
                 + collect_submodules("fm_moneyball"))

# informacje o pliku (Wlasciwosci -> Szczegoly w Windows)
plik_wersji = Path(workpath) / "wersja.txt"
plik_wersji.parent.mkdir(parents=True, exist_ok=True)
plik_wersji.write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={CZESCI}, prodvers={CZESCI}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('041504B0', [
          StringStruct('CompanyName', 'Hubihp'),
          StringStruct('FileDescription', 'FM26 Moneyball'),
          StringStruct('FileVersion', '{WERSJA}'),
          StringStruct('ProductName', 'FM26 Moneyball'),
          StringStruct('ProductVersion', '{WERSJA}'),
          StringStruct('OriginalFilename', 'FM26Moneyball.exe')])]),
        VarFileInfo([VarStruct('Translation', [0x0415, 1200])])]
)""", encoding="utf-8")

a = Analysis(
    ["fm26_moneyball.py"],
    datas=datas,
    hiddenimports=hiddenimports,
    # biblioteki wykresow i narzedzia deweloperskie nie sa potrzebne w programie
    excludes=["streamlit", "altair", "plotly", "matplotlib", "tkinter", "pytest", "IPython", "PyQt5", "PyQt6",
              "PySide2", "PySide6", "gi"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="FM26Moneyball",
    icon="assets/fm26.ico",
    version=str(plik_wersji),
    console=False,          # bez czarnego okna; komunikaty w okienkach, dziennik w ~/.fm_moneyball/logi
    upx=False,              # UPX zwieksza ryzyko falszywych alarmow antywirusa
)
coll = COLLECT(exe, a.binaries, a.datas, name="FM26Moneyball", upx=False)
