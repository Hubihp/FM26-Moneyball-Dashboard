"""Punkt wejscia dla wersji .exe (PyInstaller) - to samo co `python -m fm_moneyball`."""
from fm_moneyball.__main__ import main

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()       # proces pomocniczy w .exe (PyInstaller) - przed czymkolwiek innym
    main()
