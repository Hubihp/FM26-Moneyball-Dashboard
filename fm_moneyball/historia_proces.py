"""
Migawki historii ze starszych zapisow folderu - odczyt w osobnym procesie.

Odczyt zapisu to ok. 40 s pracy procesora w Pythonie. W watku serwera zabieralby GIL i spowalnial kazde zapytanie
interfejsu, wiec starsze zapisy czyta osobny proces (multiprocessing, "spawn" - tak samo w Windows i w .exe).
Gdy procesu nie da sie uruchomic, odczyt wraca do watku serwera (jak w wersji 2.0).
"""
import logging
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool

log = logging.getLogger("fm_moneyball")

# wyniki odczytu jednego zapisu
OK, INNA_KARIERA, BLAD, PRZEJSCIOWY = "ok", "inna kariera", "błąd", "przejściowy"


def migawka_z_zapisu(sciezka, opcje, menedzer, katalog, plik_nazw, plik_mnoznikow, plik_krajow):
    """
    Jeden starszy zapis -> migawka historii w katalogu kariery. Zwraca (wynik, czy dodano migawke, opis bledu).
    Zapis innej kariery (inny menedzer) nie daje migawki. Wolane w procesie potomnym albo (zapasowo) w watku.
    """
    from fm_moneyball import historia
    from fm_moneyball.serwer.stan import przygotuj_dane
    from fm_moneyball.zrodla.zapis_fm import wczytaj_zapis
    try:
        wynik = wczytaj_zapis(sciezka, opcje)
        if wynik.menedzer != menedzer:
            return INNA_KARIERA, False, None
        dane, _, _ = przygotuj_dane(wynik.dane, wynik.ligi, wynik.kraje_auto, wynik.kraje_baza,
                                    plik_nazw, plik_mnoznikow, plik_krajow)
        return OK, historia.zapisz_migawke(katalog, dane, wynik.data_gry) is not None, None
    except (OSError, MemoryError) as e:   # plik zablokowany, brak pamieci - do ponowienia przy kolejnym wczytaniu
        return PRZEJSCIOWY, False, f"{type(e).__name__}: {e}"
    except Exception as e:                 # uszkodzony albo obcy zapis - zapamietany, zeby go nie czytac ponownie
        return BLAD, False, f"{type(e).__name__}: {e}"


def _proba_procesu():
    return 42


def pula_procesow():
    """Jednoprocesowa pula ("spawn") albo None, gdy procesu potomnego nie da sie uruchomic."""
    try:
        return ProcessPoolExecutor(max_workers=1, mp_context=multiprocessing.get_context("spawn"))
    except (OSError, ValueError, NotImplementedError) as e:
        log.warning("Historia z folderu: brak procesu pomocniczego (%s) - odczyt w watku", e)
        return None


def w_procesie(pula, *argumenty):
    """migawka_z_zapisu w puli procesow; None, gdy proces zawiodl (wtedy odczyt w watku)."""
    try:
        return pula.submit(migawka_z_zapisu, *argumenty).result()
    except (BrokenProcessPool, OSError, RuntimeError) as e:
        log.warning("Historia z folderu: proces pomocniczy zawiódł (%s) - odczyt w wątku", e)
        return None


def test_procesu():
    """Sprawdzenie (CI, --test-procesu): proces potomny startuje i zwraca wynik. Kod wyjscia 0 = dziala."""
    pula = pula_procesow()
    if pula is None:
        return 1
    try:
        return 0 if pula.submit(_proba_procesu).result(timeout=120) == 42 else 1
    except Exception as e:
        print(f"Proces pomocniczy nie działa: {e}")
        return 1
    finally:
        pula.shutdown(cancel_futures=True)
