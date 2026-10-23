@echo off
setlocal
REM Aktualizacja FM26 Moneyball bez gita: pobiera najnowsza wersje z GitHuba i nadpisuje pliki aplikacji.
REM Twoje dane (nazwy lig i krajow, ustawienia, cache) sa w %USERPROFILE%\.fm_moneyball i zostaja bez zmian.

set "GALAZ=claude/optimistic-lamport-we8t1j"
set "URL=https://github.com/Hubihp/FM26-Moneyball-Dashboard/archive/refs/heads/%GALAZ%.zip"
set "CEL=%~dp0"
set "ZIP=%TEMP%\fm26_moneyball.zip"
set "ROZPAK=%TEMP%\fm26_moneyball_aktualizacja"

echo.
echo === Aktualizacja FM26 Moneyball ===
echo Jesli aplikacja jest uruchomiona, zamknij ja najpierw (Ctrl+C w jej oknie).
echo.

echo [1/4] Pobieranie najnowszej wersji...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri '%URL%' -OutFile '%ZIP%' -UseBasicParsing } catch { exit 1 }"
if errorlevel 1 (
    echo BLAD: nie udalo sie pobrac aktualizacji. Sprawdz polaczenie z internetem.
    goto :koniec_blad
)

echo [2/4] Rozpakowywanie...
if exist "%ROZPAK%" rmdir /s /q "%ROZPAK%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Expand-Archive -Path '%ZIP%' -DestinationPath '%ROZPAK%' -Force } catch { exit 1 }"
if errorlevel 1 (
    echo BLAD: nie udalo sie rozpakowac pobranego pliku.
    goto :koniec_blad
)

set "ZRODLO="
for /d %%F in ("%ROZPAK%\*") do set "ZRODLO=%%F"
if not defined ZRODLO (
    echo BLAD: pobrany plik ma nieoczekiwana zawartosc.
    goto :koniec_blad
)

echo [3/4] Kopiowanie plikow do %CEL%
robocopy "%ZRODLO%" "%CEL%." /E /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (
    echo BLAD: nie udalo sie skopiowac plikow. Czy aplikacja jest na pewno zamknieta?
    goto :koniec_blad
)

echo [4/4] Sprawdzanie bibliotek Pythona...
py -m pip install -r "%CEL%requirements.txt" --quiet --disable-pip-version-check
if errorlevel 1 echo Uwaga: instalacja bibliotek zglosila problem - uruchom recznie: py -m pip install -r requirements.txt

rmdir /s /q "%ROZPAK%" 2>nul
del "%ZIP%" 2>nul
echo.
echo Gotowe. Uruchom aplikacje: py -m fm_moneyball
echo W przegladarce odswiez strone (Ctrl+F5).
echo.
pause
exit /b 0

:koniec_blad
echo.
pause
exit /b 1
