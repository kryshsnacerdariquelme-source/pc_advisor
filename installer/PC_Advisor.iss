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
; Terminos y condiciones (primera pagina de aceptacion). La politica de
; privacidad se acepta en una segunda pagina, creada en la seccion [Code].
LicenseFile=..\legal\TERMINOS_Y_CONDICIONES.txt
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\PC_Advisor\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Se extrae solo durante la instalacion para mostrarla en el asistente
Source: "..\legal\POLITICA_DE_PRIVACIDAD.txt"; Flags: dontcopy

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
var
  PaginaPrivacidad: TWizardPage;
  MemoPrivacidad: TNewMemo;
  RbAcepto, RbNoAcepto: TNewRadioButton;

procedure PrivacidadClick(Sender: TObject);
begin
  WizardForm.NextButton.Enabled := RbAcepto.Checked;
end;

procedure InitializeWizard;
var
  Archivo: String;
begin
  // Segunda pagina de aceptacion: Politica de privacidad (va despues de los Terminos)
  PaginaPrivacidad := CreateCustomPage(wpLicense, 'Política de privacidad',
    'Lee cómo PC Advisor trata tu información antes de continuar.');

  MemoPrivacidad := TNewMemo.Create(PaginaPrivacidad);
  MemoPrivacidad.Parent := PaginaPrivacidad.Surface;
  MemoPrivacidad.Left := 0;
  MemoPrivacidad.Top := 0;
  MemoPrivacidad.Width := PaginaPrivacidad.SurfaceWidth;
  MemoPrivacidad.Height := PaginaPrivacidad.SurfaceHeight - ScaleY(56);
  MemoPrivacidad.ScrollBars := ssVertical;
  MemoPrivacidad.ReadOnly := True;
  MemoPrivacidad.WordWrap := True;
  ExtractTemporaryFile('POLITICA_DE_PRIVACIDAD.txt');
  Archivo := ExpandConstant('{tmp}\POLITICA_DE_PRIVACIDAD.txt');
  MemoPrivacidad.Lines.LoadFromFile(Archivo);

  RbAcepto := TNewRadioButton.Create(PaginaPrivacidad);
  RbAcepto.Parent := PaginaPrivacidad.Surface;
  RbAcepto.Left := 0;
  RbAcepto.Top := MemoPrivacidad.Top + MemoPrivacidad.Height + ScaleY(8);
  RbAcepto.Width := PaginaPrivacidad.SurfaceWidth;
  RbAcepto.Caption := 'Acepto la política de privacidad';
  RbAcepto.OnClick := @PrivacidadClick;

  RbNoAcepto := TNewRadioButton.Create(PaginaPrivacidad);
  RbNoAcepto.Parent := PaginaPrivacidad.Surface;
  RbNoAcepto.Left := 0;
  RbNoAcepto.Top := RbAcepto.Top + ScaleY(22);
  RbNoAcepto.Width := PaginaPrivacidad.SurfaceWidth;
  RbNoAcepto.Caption := 'No acepto la política de privacidad';
  RbNoAcepto.Checked := True;
  RbNoAcepto.OnClick := @PrivacidadClick;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = PaginaPrivacidad.ID then
    WizardForm.NextButton.Enabled := RbAcepto.Checked
  else if CurPageID <> wpLicense then
    WizardForm.NextButton.Enabled := True;
end;

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
