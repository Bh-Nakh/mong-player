; 몽플레이어 설치 스크립트 (Inno Setup 6). setup.bat 이 /DSrcDir=<dist\몽플레이어 폴더> /DAppVersion=<VERSION 파일 내용> 으로 실행한다.
; (PyInstaller 로 만든 dist 폴더를 그대로 담는다. 폴더가 커서 압축에 시간이 걸린다.)
#ifndef SrcDir
  #define SrcDir "..\dist\몽플레이어"
#endif
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppName "몽플레이어"
#define AppExe "몽플레이어.exe"
#define ProtoId "mongplayer"

[Setup]
AppId={{B82BE76D-81FB-4892-946E-B31887B739BF}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=NoAd
; 자동 업데이트(패치)가 설치 폴더에 파일을 쓰므로 쓰기 가능한 사용자 폴더(%LOCALAPPDATA%\Programs)에만 설치한다.
DefaultDirName={autopf}\{#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\setup
OutputBaseFilename=몽플레이어-Setup-{#AppVersion}
SetupIconFile=..\noadplayer\resources\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/normal
SolidCompression=yes
WizardStyle=modern
ChangesAssociations=yes
CloseApplications=yes
RestartApplications=no
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}
VersionInfoCompany=NoAd

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SrcDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; 홈페이지(설치 확인 페이지)의 [실행] 버튼이 쓰는 프로토콜. 제거할 때 함께 지운다.
Root: HKA; Subkey: "Software\Classes\{#ProtoId}"; ValueType: string; ValueName: ""; ValueData: "URL:{#AppName}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\{#ProtoId}"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\{#ProtoId}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"""

[Run]
; 우클릭 메뉴·파일 연결은 앱이 처음 실행할 때 스스로 등록한다(shell_register.ensure_registered).
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; 제거할 때 앱이 등록한 우클릭 메뉴·파일 연결을 앱 스스로 지우게 한다.
Filename: "{app}\{#AppExe}"; Parameters: "--unregister"; RunOnceId: "MongPlayerUnregister"; Flags: runhidden skipifdoesntexist
