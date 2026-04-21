; TradeAdviser Desktop - Windows Installer (NSIS)
; Usage: makensis tradeadviser-installer.nsi

!define VERSION "1.0.0"
!define APPNAME "TradeAdviser"
!define COMPANYNAME "TradeAdviser"
!define DESCRIPTION "Professional Trading Platform with Quant Analytics"
!define INSTALLSIZE 450000  ; ~450 MB estimated

; Set compression
SetCompressor /SOLID lzma

; Request admin privileges
RequestExecutionLevel admin

; Modern UI
!include "MUI2.nsh"
!include "x64.nsh"

; Variables
Var StartMenuFolder

; Settings
Name "${APPNAME} ${VERSION}"
OutFile "TradeAdviser-v${VERSION}-installer.exe"
InstallDir "$PROGRAMFILES64\${APPNAME}"
InstallDirRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" "InstallLocation"

; MUI Settings
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_STARTMENU Application $StartMenuFolder
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_LANGUAGE "English"

; Installer sections
Section "Install"
  SetOutPath "$INSTDIR"
  
  ; Copy application files
  File "dist\TradeAdviser.exe"
  File "assets\icon.ico"
  File /r "config\*.*"
  
  ; Create registry entries
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
    "DisplayName" "${APPNAME} ${VERSION}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
    "UninstallString" "$INSTDIR\uninstall.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
    "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
    "DisplayVersion" "${VERSION}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
    "Publisher" "${COMPANYNAME}"
  
  ; Create uninstaller
  WriteUninstaller "$INSTDIR\uninstall.exe"
  
  ; Create shortcuts
  !insertmacro MUI_STARTMENU_WRITE_BEGIN Application
  CreateDirectory "$SMPROGRAMS\$StartMenuFolder"
  CreateShortCut "$SMPROGRAMS\$StartMenuFolder\${APPNAME}.lnk" "$INSTDIR\TradeAdviser.exe" \
    "" "$INSTDIR\icon.ico" 0 SW_SHOWNORMAL "Professional Trading Platform"
  CreateShortCut "$SMPROGRAMS\$StartMenuFolder\Uninstall ${APPNAME}.lnk" "$INSTDIR\uninstall.exe"
  !insertmacro MUI_STARTMENU_WRITE_END
  
  ; Create desktop shortcut (optional)
  CreateShortCut "$DESKTOP\${APPNAME}.lnk" "$INSTDIR\TradeAdviser.exe" \
    "" "$INSTDIR\icon.ico" 0 SW_SHOWNORMAL
SectionEnd

; Uninstaller section
Section "Uninstall"
  ; Remove files
  Delete "$INSTDIR\TradeAdviser.exe"
  Delete "$INSTDIR\icon.ico"
  Delete "$INSTDIR\uninstall.exe"
  RMDir /r "$INSTDIR\config"
  RMDir "$INSTDIR"
  
  ; Remove shortcuts
  !insertmacro MUI_STARTMENU_GETFOLDER Application $StartMenuFolder
  RMDir /r "$SMPROGRAMS\$StartMenuFolder"
  Delete "$DESKTOP\${APPNAME}.lnk"
  
  ; Remove registry entries
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}"
SectionEnd
