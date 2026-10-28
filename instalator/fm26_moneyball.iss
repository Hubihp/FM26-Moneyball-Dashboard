; Instalator FM26 Moneyball (Inno Setup 6). Buduje go workflow .github/workflows/exe.yml:
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
AppName=FM26 Moneyball
AppVersion={#Wersja}
AppVerName=FM26 Moneyball {#Wersja}
AppPublisher=Hubihp
AppPublisherURL=https://github.com/Hubihp/FM26-Moneyball-Dashboard
AppUpdatesURL=https://github.com/Hubihp/FM26-Moneyball-Dashboard/releases
DefaultDirName={localappdata}\Programs\FM26 Moneyball
DefaultGroupName=FM26 Moneyball
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=FM26Moneyball-Setup
SetupIconFile=..\assets\fm26.ico
UninstallDisplayIcon={app}\FM26Moneyball.exe
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

[Files]
Source: "..\dist\FM26Moneyball\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\FM26 Moneyball"; Filename: "{app}\FM26Moneyball.exe"
Name: "{autodesktop}\FM26 Moneyball"; Filename: "{app}\FM26Moneyball.exe"; Tasks: pulpit

[Run]
Filename: "{app}\FM26Moneyball.exe"; Description: "Uruchom FM26 Moneyball"; Flags: nowait postinstall skipifsilent
Filename: "{app}\FM26Moneyball.exe"; Flags: nowait skipifnotsilent
