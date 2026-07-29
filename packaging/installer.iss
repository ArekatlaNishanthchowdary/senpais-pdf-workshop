; Inno Setup script for Senpai's Pdf Workshop.
;
; Bundles the app (built by PyInstaller into dist\SenpaisPdfWorkshop) together
; with Ghostscript, LibreOffice, and Tesseract installers, so the three
; external-binary operations (compress/PDF-A, Office->PDF, OCR) work out of
; the box instead of requiring the user to separately find and install each
; one. Skips any tool already present, and adds every tool's bin directory to
; the system PATH -- installing a tool doesn't reliably do that on its own
; (Ghostscript and LibreOffice didn't during this project's own dev setup).

#define AppName "Senpai's Pdf Workshop"
#define AppVersion "0.1.0"
#define AppExeName "SenpaisPdfWorkshop.exe"
#define DistDir "..\dist\SenpaisPdfWorkshop"
#define BundleDir "bundled"

[Setup]
AppId={{8F2C6C1E-3B4A-4E7D-9F1A-6C2D8E5B7A90}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}
OutputDir=..\dist\installer
OutputBaseFilename=SenpaisPdfWorkshopSetup
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
WizardStyle=modern
DisableWelcomePage=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
; the app itself
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

; bundled third-party installers -- pre-compressed binaries, no point re-compressing
Source: "{#BundleDir}\gs10071w64.exe"; DestDir: "{tmp}"; Flags: dontcopy deleteafterinstall
Source: "{#BundleDir}\tesseract-setup.exe"; DestDir: "{tmp}"; Flags: dontcopy deleteafterinstall
Source: "{#BundleDir}\LibreOffice_Win_x86-64.msi"; DestDir: "{tmp}"; Flags: dontcopy deleteafterinstall

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
; Adds the app to the "Open with" list for .pdf files -- additive only,
; does NOT make it the default PDF handler (that would need HKCR\.pdf
; itself, a bigger and more surprising change than "show up as an option").
; The whole Applications\<exe> key (and everything under it) is removed on
; uninstall via uninsdeletekey.
Root: HKCR; Subkey: "Applications\{#AppExeName}"; Flags: uninsdeletekey
Root: HKCR; Subkey: "Applications\{#AppExeName}"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "{#AppName}"
Root: HKCR; Subkey: "Applications\{#AppExeName}\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"",0"
Root: HKCR; Subkey: "Applications\{#AppExeName}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""
Root: HKCR; Subkey: "Applications\{#AppExeName}\SupportedTypes"; ValueType: string; ValueName: ".pdf"; ValueData: ""

[Run]
; extract bundled installers to temp only when actually needed (dontcopy above
; means they're not pre-extracted; ExtractTemporaryFile pulls each one out
; just before it runs, so a machine that already has everything never pays
; the extraction cost)
Filename: "{tmp}\gs10071w64.exe"; Parameters: "/S"; \
    StatusMsg: "Installing Ghostscript (needed for Compress and PDF/A)..."; \
    Check: NeedGhostscript; Flags: skipifdoesntexist waituntilterminated

Filename: "{tmp}\tesseract-setup.exe"; Parameters: "/S"; \
    StatusMsg: "Installing Tesseract (needed for OCR)..."; \
    Check: NeedTesseract; Flags: skipifdoesntexist waituntilterminated

Filename: "msiexec.exe"; Parameters: "/i ""{tmp}\LibreOffice_Win_x86-64.msi"" /qb! /norestart"; \
    StatusMsg: "Installing LibreOffice (needed for Office document conversion)..."; \
    Check: NeedLibreOffice; Flags: waituntilterminated

Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
var
  GhostscriptBinDir, LibreOfficeBinDir, TesseractBinDir: string;
  GhostscriptFound, LibreOfficeFound, TesseractFound: Boolean;

function FindGhostscriptBinDir(var BinDir: string): Boolean;
var
  FindRec: TFindRec;
  Base: string;
begin
  Result := False;
  Base := ExpandConstant('{pf}') + '\gs';
  if DirExists(Base) then
  begin
    if FindFirst(Base + '\*', FindRec) then
    begin
      try
        repeat
          if (FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY <> 0)
             and (FindRec.Name <> '.') and (FindRec.Name <> '..')
             and FileExists(Base + '\' + FindRec.Name + '\bin\gswin64c.exe') then
          begin
            BinDir := Base + '\' + FindRec.Name + '\bin';
            Result := True;
            Exit;
          end;
        until not FindNext(FindRec);
      finally
        FindClose(FindRec);
      end;
    end;
  end;
end;

function IsOnPath(const ExeName: string): Boolean;
var
  Paths: string;
  PathList: TStringList;
  I: Integer;
begin
  Result := False;
  if not RegQueryStringValue(HKEY_LOCAL_MACHINE,
       'SYSTEM\CurrentControlSet\Control\Session Manager\Environment', 'Path', Paths) then
    Exit;
  PathList := TStringList.Create;
  try
    PathList.Delimiter := ';';
    PathList.StrictDelimiter := True;
    PathList.DelimitedText := Paths;
    for I := 0 to PathList.Count - 1 do
      if FileExists(AddBackslash(PathList[I]) + ExeName) then
      begin
        Result := True;
        Exit;
      end;
  finally
    PathList.Free;
  end;
end;

// ponytail: covers "installed but never added to PATH", the exact state this
// project's own dev machine was in for Ghostscript/LibreOffice after a plain
// manual install -- checking only PATH would re-run installers needlessly.
function NeedGhostscript: Boolean;
begin
  GhostscriptFound := FindGhostscriptBinDir(GhostscriptBinDir) or IsOnPath('gswin64c.exe');
  Result := not GhostscriptFound;
end;

function NeedLibreOffice: Boolean;
begin
  LibreOfficeBinDir := ExpandConstant('{pf}') + '\LibreOffice\program';
  LibreOfficeFound := FileExists(LibreOfficeBinDir + '\soffice.exe') or IsOnPath('soffice.exe');
  Result := not LibreOfficeFound;
end;

function NeedTesseract: Boolean;
begin
  TesseractBinDir := ExpandConstant('{pf}') + '\Tesseract-OCR';
  TesseractFound := FileExists(TesseractBinDir + '\tesseract.exe') or IsOnPath('tesseract.exe');
  Result := not TesseractFound;
end;

procedure AddToSystemPath(Dir: string);
var
  Paths: string;
begin
  if Dir = '' then Exit;
  if not RegQueryStringValue(HKEY_LOCAL_MACHINE,
       'SYSTEM\CurrentControlSet\Control\Session Manager\Environment', 'Path', Paths) then
    Paths := '';
  if Pos(';' + Uppercase(Dir) + ';', ';' + Uppercase(Paths) + ';') = 0 then
  begin
    if (Paths <> '') and (Paths[Length(Paths)] <> ';') then
      Paths := Paths + ';';
    Paths := Paths + Dir;
    RegWriteStringValue(HKEY_LOCAL_MACHINE,
      'SYSTEM\CurrentControlSet\Control\Session Manager\Environment', 'Path', Paths);
  end;
end;

procedure ExtractInstallers;
begin
  if NeedGhostscript then
    ExtractTemporaryFile('gs10071w64.exe');
  if NeedTesseract then
    ExtractTemporaryFile('tesseract-setup.exe');
  if NeedLibreOffice then
    ExtractTemporaryFile('LibreOffice_Win_x86-64.msi');
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    ExtractInstallers;

  if CurStep = ssPostInstall then
  begin
    // re-check post-install: a tool just installed now has its real bin dir
    if NeedGhostscript then ; // no-op, keeps GhostscriptBinDir from the pre-check
    if GhostscriptBinDir = '' then
      FindGhostscriptBinDir(GhostscriptBinDir);
    AddToSystemPath(GhostscriptBinDir);
    AddToSystemPath(ExpandConstant('{pf}') + '\LibreOffice\program');
    AddToSystemPath(ExpandConstant('{pf}') + '\Tesseract-OCR');
  end;
end;
