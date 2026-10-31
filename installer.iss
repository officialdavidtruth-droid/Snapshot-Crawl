#define MyAppName "Snapshot Crawl"
#define MyAppVersion "4.0.3"
#define MyAppExeName "Snapshot Crawl.exe"
[Setup]
AppId={{8BFBF4B2-4A79-4E2B-A4CB-7ACD9F48BEE2}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\Snapshot Crawl
DefaultGroupName={#MyAppName}
OutputDir=installer-output
OutputBaseFilename=Snapshot-Crawl-V4.3-Setup
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
[Files]
Source: "dist\Snapshot Crawl\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"
[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Snapshot Crawl"; Flags: postinstall nowait skipifsilent
