"""Generación de artefactos de despliegue del certificado CA.

Genera tres archivos listos para usar, con el certificado CA real embebido:
- install-cert.bat     : instalador de doble clic para Windows (cualquier equipo)
- deploy-gpo.ps1       : script PowerShell para desplegar vía GPO en Active Directory
- cert.mobileconfig    : perfil para iOS/macOS
"""

import uuid
from pathlib import Path

CA_CERT_PATH = "/etc/squid/ssl_cert/squid-ca.crt"


class CaCertNotFound(Exception):
    pass


def _read_pem():
    try:
        return Path(CA_CERT_PATH).read_text()
    except FileNotFoundError:
        raise CaCertNotFound("Certificado CA no encontrado. Reinicia el contenedor Squid.")


def _pem_lines(pem):
    return [l.strip() for l in pem.splitlines() if l.strip()]


def _der_base64(pem):
    """Extrae el cuerpo base64 (DER) del PEM, sin los marcadores BEGIN/END."""
    return "".join(l for l in _pem_lines(pem) if not l.startswith("-----"))


def generate_bat_installer():
    """Genera install-cert.bat — instalador de doble clic para Windows."""
    pem = _read_pem()
    lines = _pem_lines(pem)

    echo_block = "\n".join("echo " + line for line in lines)

    template = """@echo off
setlocal
echo ============================================
echo  SquidManager - Instalador de certificado CA
echo ============================================
echo.
echo Instalando el certificado raiz en este equipo...

set CERT_FILE=%TEMP%\\squidmanager-ca.crt

rem Escribir el certificado a un archivo temporal
(
__CERT_LINES__
) > "%CERT_FILE%"

rem Instalar en el almacen de confianza del sistema (requiere admin)
certutil -addstore -f "Root" "%CERT_FILE%" >nul 2>&1

if %errorlevel%==0 (
    echo.
    echo [OK] Certificado instalado correctamente.
    echo El proxy ya no mostrara advertencias de seguridad.
) else (
    echo.
    echo [ERROR] No se pudo instalar el certificado.
    echo Cierra esta ventana, haz clic derecho sobre este archivo
    echo y elige "Ejecutar como administrador".
)

echo.
pause
"""
    return template.replace("__CERT_LINES__", echo_block)


def generate_gpo_script():
    """Genera deploy-gpo.ps1 — script para desplegar el certificado vía GPO."""
    pem = _read_pem()
    der_b64 = _der_base64(pem)

    template = """<#
================================================================
 SquidManager - Despliegue de certificado CA via GPO
================================================================
 EJECUTAR EN EL DOMAIN CONTROLLER con permisos de administrador
 de dominio (Domain Admin).

 Que hace este script:
   1. Escribe el certificado en el share NETLOGON (accesible por todos)
   2. Crea un GPO llamado "SquidManager Root CA"
   3. Le asigna un script de inicio que instala el certificado
      en cada equipo del dominio al arrancar
   4. Vincula el GPO al dominio

 Requisitos: ejecutar como Domain Admin en el DC.
================================================================
#>

$ErrorActionPreference = "Stop"

$GpoName = "SquidManager Root CA"
$Domain = $env:USERDNSDOMAIN
if (-not $Domain) { throw "No se pudo detectar el dominio. Ejecuta en el Domain Controller." }

$CertBase64 = @"
__CERT_DER_B64__
"@

Write-Host "1/4 Escribiendo certificado en NETLOGON..." -ForegroundColor Cyan
$netlogonPath = "\\\\$Domain\\NETLOGON\\squidmanager-ca.crt"
[IO.File]::WriteAllBytes($netlogonPath, [Convert]::FromBase64String($CertBase64))
Write-Host "    Certificado copiado a $netlogonPath" -ForegroundColor Green

Write-Host "2/4 Importando modulo GroupPolicy..." -ForegroundColor Cyan
Import-Module GroupPolicy -ErrorAction Stop

Write-Host "3/4 Creando GPO '$GpoName'..." -ForegroundColor Cyan
$existing = Get-GPO -Name $GpoName -ErrorAction SilentlyContinue
if (-not $existing) {
    $gpo = New-GPO -Name $GpoName -Comment "Confia en la CA de SquidManager para filtrado HTTPS"
} else {
    Write-Host "    El GPO ya existe, se reutilizara." -ForegroundColor Yellow
    $gpo = $existing
}

$gpoGuid = $gpo.Id.ToString()

# Escribir el script de inicio en la carpeta Sysvol del GPO
$startupDir = "\\\\$Domain\\SysVol\\$Domain\\Policies\\{$gpoGuid}\\Machine\\Scripts\\Startup"
New-Item -ItemType Directory -Path $startupDir -Force | Out-Null

$startupScript = @"
@echo off
certutil -addstore -f "Root" "\\\\$Domain\\NETLOGON\\squidmanager-ca.crt" >nul 2>&1
"@
[IO.File]::WriteAllText("$startupDir\\install-cert.cmd", $startupScript)

# Registrar el script de inicio en el GPO
Set-GPStartupScript -Name $GpoName -ScriptName "install-cert.cmd"

Write-Host "4/4 Vinculando GPO al dominio..." -ForegroundColor Cyan
$domainDN = "DC=" + ($Domain -replace "\\.", ",DC=")
New-GPLink -Name $GpoName -Target $domainDN -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "==============================================" -ForegroundColor Green
Write-Host "  Despliegue completado." -ForegroundColor Green
Write-Host "==============================================" -ForegroundColor Green
Write-Host ""
Write-Host "El certificado se instalara automaticamente en todos los"
Write-Host "equipos del dominio en el proximo reinicio (o tras 'gpupdate /force')."
Write-Host ""
Write-Host "Para forzar la aplicacion inmediata en un equipo:"
Write-Host "    gpupdate /force"
Write-Host ""
"""
    return template.replace("__CERT_DER_B64__", der_b64)


def generate_mobileconfig():
    """Genera cert.mobileconfig — perfil para iOS/macOS."""
    pem = _read_pem()
    der_b64 = _der_base64(pem)
    u1 = str(uuid.uuid4()).upper()
    u2 = str(uuid.uuid4()).upper()

    template = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>PayloadContent</key>
  <array>
    <dict>
      <key>PayloadCertificateFileName</key>
      <string>squidmanager-ca.crt</string>
      <key>PayloadContent</key>
      <data>
__CERT_DER_B64__
      </data>
      <key>PayloadDescription</key>
      <string>Confia en la CA de SquidManager para filtrado HTTPS</string>
      <key>PayloadDisplayName</key>
      <string>SquidManager Root CA</string>
      <key>PayloadIdentifier</key>
      <string>com.squidmanager.ca</string>
      <key>PayloadType</key>
      <string>com.apple.security.root</string>
      <key>PayloadUUID</key>
      <string>__UUID1__</string>
      <key>PayloadVersion</key>
      <integer>1</integer>
    </dict>
  </array>
  <key>PayloadDisplayName</key>
  <string>SquidManager Root CA</string>
  <key>PayloadIdentifier</key>
  <string>com.squidmanager.profile</string>
  <key>PayloadRemovalDisallowed</key>
  <false/>
  <key>PayloadType</key>
  <string>Configuration</string>
  <key>PayloadUUID</key>
  <string>__UUID2__</string>
  <key>PayloadVersion</key>
  <integer>1</integer>
</dict>
</plist>
"""
    return template.replace("__CERT_DER_B64__", der_b64).replace("__UUID1__", u1).replace("__UUID2__", u2)
