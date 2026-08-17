#ifndef SourceRoot
  #error SourceRoot is required
#endif
#ifndef BuildRoot
  #error BuildRoot is required
#endif
#ifndef OutputDir
  #error OutputDir is required
#endif
#ifndef AppVersion
  #define AppVersion "0.5.0"
#endif

[Setup]
AppId={{B9869426-A6FC-4D12-B7D5-FB4878E5177E}
AppName=PacheVideo
AppVersion={#AppVersion}
AppVerName=PacheVideo {#AppVersion}
AppPublisher=Pachecoins
AppPublisherURL=https://github.com/Pachecoins/PacheVideoPlugin
AppSupportURL=https://github.com/Pachecoins/PacheVideoPlugin/issues
AppUpdatesURL=https://github.com/Pachecoins/PacheVideoPlugin/releases
DefaultDirName={autopf}\PacheVideo
DefaultGroupName=PacheVideo
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\PacheVideo\PacheVideo.exe
OutputDir={#OutputDir}
OutputBaseFilename=PacheVideo-Setup-Windows-x64
SetupIconFile={#BuildRoot}\PacheVideo.ico
WizardStyle=modern dynamic
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=commandline
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
Compression=lzma2/ultra64
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
UsePreviousTasks=yes
LicenseFile={#SourceRoot}\THIRD_PARTY_NOTICES.md

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "autostart"; Description: "Iniciar PacheVideo Helper automáticamente con Windows"; GroupDescription: "Opciones:"; Flags: checkedonce
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Opciones:"; Flags: unchecked

[InstallDelete]
Type: filesandordirs; Name: "{app}\PacheVideo"
Type: filesandordirs; Name: "{app}\PacheVideoHelper"

[Files]
Source: "{#BuildRoot}\pyinstaller-dist\PacheVideo\*"; DestDir: "{app}\PacheVideo"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#BuildRoot}\pyinstaller-dist\PacheVideoHelper\*"; DestDir: "{app}\PacheVideoHelper"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceRoot}\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\PacheVideo"; Filename: "{app}\PacheVideo\PacheVideo.exe"; WorkingDir: "{app}\PacheVideo"
Name: "{group}\Desinstalar PacheVideo"; Filename: "{uninstallexe}"
Name: "{autodesktop}\PacheVideo"; Filename: "{app}\PacheVideo\PacheVideo.exe"; WorkingDir: "{app}\PacheVideo"; Tasks: desktopicon

[Registry]
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "PacheVideoHelper"; ValueData: """{app}\PacheVideoHelper\PacheVideoHelper.exe"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\PacheVideoHelper\PacheVideoHelper.exe"; Description: "Iniciar PacheVideo Helper"; Flags: nowait runhidden
Filename: "{app}\PacheVideo\PacheVideo.exe"; Description: "Abrir PacheVideo"; Flags: nowait postinstall skipifsilent; WorkingDir: "{app}\PacheVideo"

[Code]
procedure StopInstalledProcesses();
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM PacheVideoHelper.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM PacheVideo.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopInstalledProcesses();
  Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    StopInstalledProcesses();
end;
