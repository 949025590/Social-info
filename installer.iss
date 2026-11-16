[Setup]
AppName=Social Info
AppVersion=0.1.0
AppPublisher=Social Info
AppPublisherURL=https://github.com/949025590/Social-info
DefaultDirName={localappdata}\Programs\SocialInfo
DefaultGroupName=Social Info
PrivilegesRequired=lowest
OutputDir=dist\installer
OutputBaseFilename=SocialInfo-Setup
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\SocialInfo.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务"
Name: "startupicon"; Description: "开机自动启动"; GroupDescription: "附加任务"; Flags: unchecked

[Files]
Source: "dist\SocialInfo\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Social Info"; Filename: "{app}\SocialInfo.exe"
Name: "{autodesktop}\Social Info"; Filename: "{app}\SocialInfo.exe"; Tasks: desktopicon
Name: "{userstartup}\Social Info"; Filename: "{app}\SocialInfo.exe"; Tasks: startupicon

[Run]
Filename: "{app}\SocialInfo.exe"; Description: "立即启动 Social Info"; Flags: nowait postinstall skipifsilent
