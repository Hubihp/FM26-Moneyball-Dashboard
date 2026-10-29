; Instalator FM27 Dashboard (Inno Setup 6). Buduje go workflow .github/workflows/exe.yml:
;   iscc /DWersja=1.2.3 instalator\fm26_moneyball.iss
; Instalacja dla biezacego uzytkownika (bez uprawnien administratora) w %LOCALAPPDATA%\Programs.
; Dane uzytkownika sa w %USERPROFILE%\.fm_moneyball - instalator ani deinstalator ich nie dotykaja.
; Aktualizacja z programu uruchamia ten instalator po cichu (/VERYSILENT), a po instalacji
; program startuje ponownie (wpis [Run] z flaga skipifnotsilent).

#ifndef Wersja
  #define Wersja "0.0.0"
#endif

[Setup]
; Stale AppId: nowa wersja instaluje sie w miejsce poprzedniej
AppId={{82800021-7792-432D-88BC-044E4B847D6E}
AppName=FM27 Dashboard
AppVersion={#Wersja}
AppVerName=FM27 Dashboard {#Wersja}
AppPublisher=Hubihp
AppPublisherURL=https://github.com/Hubihp/FM26-Moneyball-Dashboard
AppUpdatesURL=https://github.com/Hubihp/FM26-Moneyball-Dashboard/releases
DefaultDirName={localappdata}\Programs\FM27 Dashboard
DefaultGroupName=FM27 Dashboard
DisableProgramGroupPage=yes
; skroty zawsze pod nowa nazwa (przed 1.6.0 program nazywal sie FM26 Moneyball)
UsePreviousGroup=no
DisableDirPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=FM27Dashboard-Setup
SetupIconFile=..\assets\fm26.ico
UninstallDisplayIcon={app}\FM27Dashboard.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=force
RestartApplications=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "polski"; MessagesFile: "compiler:Languages\Polish.isl"

[Tasks]
Name: "pulpit"; Description: "Skrót na pulpicie"; GroupDescription: "Skróty:"

[InstallDelete]
; stare pliki programu (np. biblioteki z poprzedniej wersji) - tylko folder programu, nie dane
Type: filesandordirs; Name: "{app}\_internal"
; pozostalosci po nazwie FM26 Moneyball (do 1.5.x): stary plik programu i skroty
Type: files; Name: "{app}\FM26Moneyball.exe"
Type: filesandordirs; Name: "{autoprograms}\FM26 Moneyball"
Type: files; Name: "{autodesktop}\FM26 Moneyball.lnk"

[Files]
Source: "..\dist\FM27Dashboard\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\FM27 Dashboard"; Filename: "{app}\FM27Dashboard.exe"
Name: "{autodesktop}\FM27 Dashboard"; Filename: "{app}\FM27Dashboard.exe"; Tasks: pulpit

[Run]
Filename: "{app}\FM27Dashboard.exe"; Description: "Uruchom FM27 Dashboard"; Flags: nowait postinstall skipifsilent
Filename: "{app}\FM27Dashboard.exe"; Flags: nowait skipifnotsilent
