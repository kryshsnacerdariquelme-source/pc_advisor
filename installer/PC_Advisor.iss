; Script de Inno Setup 6 para el instalador de PC Advisor.
; Compilar con:  build_installer.bat   (o abrir este archivo en Inno Setup y pulsar F9)

#define MyAppName "PC Advisor"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "PC Advisor"
#define MyAppExeName "PC_Advisor.exe"

[Setup]
; Identificador unico de la app (NO lo cambies entre versiones: asi las actualizaciones reemplazan a la anterior)
AppId={{2EFCAAE9-F53A-43AF-9006-BBE40A340ECB}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\installer_output
OutputBaseFilename=PC_Advisor_Setup_{#MyAppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Por defecto instala solo para el usuario actual (no pide administrador).
; El asistente permite elegir "para todos los usuarios" si se desea.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; Pantalla de terminos y privacidad: el usuario debe aceptarla para continuar
LicenseFile=TERMINOS_Y_PRIVACIDAD.txt
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\PC_Advisor\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "TERMINOS_Y_PRIVACIDAD.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// Al desinstalar, pregunta si tambien se borran el historial y los ajustes
// (carpeta %LOCALAPPDATA%\PC Advisor). Por defecto se conservan.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Carpeta: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    Carpeta := ExpandConstant('{localappdata}\PC Advisor');
    if DirExists(Carpeta) then
      if MsgBox('¿Quieres borrar también el historial y los datos de PC Advisor?', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(Carpeta, True, True, True);
  end;
end;
