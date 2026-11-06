; Compile with Inno Setup 6.4 or later on Windows.
; The stable AppId intentionally stays the same across application versions.
#define RepoRoot AddBackslash(SourcePath) + "..\.."
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef AppSourceDir
  #define AppSourceDir RepoRoot + "\dist\DataDesk"
#endif
#ifndef InstallerOutputDir
  #define InstallerOutputDir RepoRoot + "\dist\installers"
#endif

[Setup]
AppId={{9E9166A6-89CF-44F7-BAC6-29C01B85DA9D}
AppName=DataDesk
AppVersion={#AppVersion}
AppVerName=DataDesk {#AppVersion}
AppPublisher=KrAlmano
AppPublisherURL=https://github.com/KrAlmano/DataDesk
AppSupportURL=https://github.com/KrAlmano/DataDesk/issues
AppUpdatesURL=https://github.com/KrAlmano/DataDesk/actions/workflows/desktop-packages.yml
VersionInfoVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\DataDesk
DefaultGroupName=DataDesk
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
SourceDir={#AppSourceDir}
OutputDir={#InstallerOutputDir}
OutputBaseFilename=DataDesk-{#AppVersion}-windows-x64-setup
SetupIconFile={#RepoRoot}\build\icons\datadesk.ico
UninstallDisplayIcon={app}\DataDesk.exe
UninstallDisplayName=DataDesk
LicenseFile={#RepoRoot}\LICENSE
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
DisableProgramGroupPage=yes
DisableWelcomePage=no
CloseApplications=no
RestartApplications=no
AlwaysRestart=no
UsePreviousAppDir=yes
UsePreviousTasks=yes

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
turkish.DesktopShortcut=Masaüstü kısayolu oluştur
turkish.LaunchDataDesk=DataDesk uygulamasını aç
english.DesktopShortcut=Create a desktop shortcut
english.LaunchDataDesk=Launch DataDesk

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopShortcut}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\DataDesk"; Filename: "{app}\DataDesk.exe"; WorkingDir: "{app}"; AppUserModelID: "io.github.KrAlmano.DataDesk"
Name: "{autodesktop}\DataDesk"; Filename: "{app}\DataDesk.exe"; WorkingDir: "{app}"; AppUserModelID: "io.github.KrAlmano.DataDesk"; Tasks: desktopicon

[Run]
Filename: "{app}\DataDesk.exe"; Description: "{cm:LaunchDataDesk}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent unchecked

; There is deliberately no broad [UninstallDelete] entry. Inno Setup removes
; only the application files/shortcuts it installed, leaving user exports alone.
