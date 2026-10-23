# Specyfikacja PyInstallera: jeden plik FM26Moneyball.exe (Windows) z serwerem, interfejsem i danymi.
# Budowanie: pyinstaller fm26_moneyball.spec   (wynik w dist/)
# Na GitHubie buduje go workflow .github/workflows/exe.yml.
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

datas = [
    ("fm_moneyball/serwer/static", "fm_moneyball/serwer/static"),   # zbudowany interfejs React
    ("dane/*.csv", "dane"),                                         # domyslne nazwy lig i krajow
]
datas += collect_data_files("fmsave")
datas += copy_metadata("fmsave")          # fmsave.__version__ czyta metadane pakietu

hiddenimports = (collect_submodules("fmsave") + collect_submodules("uvicorn")
                 + collect_submodules("fm_moneyball"))

a = Analysis(
    ["fm26_moneyball.py"],
    datas=datas,
    hiddenimports=hiddenimports,
    # stary interfejs Streamlit i narzedzia deweloperskie nie sa potrzebne w .exe
    excludes=["streamlit", "altair", "plotly", "matplotlib", "tkinter", "pytest", "IPython"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="FM26Moneyball",
    icon="assets/fm26.ico",
    console=True,           # okno z adresem aplikacji; zamkniecie okna konczy aplikacje
    upx=False,
)
