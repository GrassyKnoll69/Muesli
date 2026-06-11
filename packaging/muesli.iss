; Inno Setup script for Muesli — per-user Windows installer.
;
; Wraps the PyInstaller onedir output (dist\Muesli\) into a single
; MuesliSetup-<version>.exe. Per-user install (no admin), Start Menu shortcut,
; optional desktop shortcut, and an optional step to download the NVIDIA CUDA
; libraries for GPU acceleration. Uninstall removes the program files but leaves
; the user's data in %USERPROFILE%\.muesli untouched.
;
; Build via build_installer.ps1 (which passes /DMyAppVersion). To compile
; directly:  iscc /DMyAppVersion=0.1.0 packaging\muesli.iss

#define MyAppName "Muesli"
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppPublisher "Muesli"
#define MyAppExeName "Muesli.exe"

[Setup]
; A stable AppId keeps upgrades/uninstall coherent across versions.
AppId={{A1B2C3D4-E5F6-47A8-9B0C-1D2E3F4A5B6C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
VersionInfoVersion={#MyAppVersion}
DefaultDirName={localappdata}\{#MyAppName}
DisableProgramGroupPage=yes
; Per-user install: no UAC/admin prompt.
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=MuesliSetup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked
; Optional GPU acceleration. Unchecked by default; the description explains it.
Name: "cuda"; Description: "Download NVIDIA CUDA libraries for GPU acceleration (~1 GB; requires an NVIDIA GPU). Makes transcription much faster. Skip this if you don't have an NVIDIA GPU — you can also enable it later from inside the app."; GroupDescription: "Optional GPU acceleration:"; Flags: unchecked

[Files]
Source: "..\dist\Muesli\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; If the user opted in, download the CUDA libraries now (hidden, with a status
; message). This can take several minutes on the first install.
Filename: "{app}\{#MyAppExeName}"; Parameters: "--download-cuda"; StatusMsg: "Downloading NVIDIA CUDA libraries (this can take several minutes)..."; Tasks: cuda; Flags: runhidden waituntilterminated
; Offer to launch on finish.
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove the program directory. User data in %USERPROFILE%\.muesli is preserved.
Type: filesandordirs; Name: "{app}"
