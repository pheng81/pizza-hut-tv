# PowerShell script to create desktop shortcut for Pizza Hut TV Pi Client

$DesktopPath = [System.Environment]::GetFolderPath('Desktop')
$WorkingDirectory = "C:\Users\toeng\Pizza Hut TV"
$TargetPath = "$WorkingDirectory\launch_pi_client.bat"
$ShortcutPath = "$DesktopPath\Pizza Hut TV Pi Client.lnk"
$ShortcutPathEATV = "$DesktopPath\EATV.lnk"

# Create WScript Shell object
$WScriptShell = New-Object -ComObject WScript.Shell

# Create shortcut
$Shortcut = $WScriptShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $TargetPath
$Shortcut.WorkingDirectory = $WorkingDirectory
$Shortcut.Description = "Pizza Hut TV Pi Client - Manage and control Pi displays"
$Shortcut.WindowStyle = 1  # Normal window

# Try to set an icon (use system video icon)
try {
    $Shortcut.IconLocation = "shell32.dll,15"  # Video/TV icon from system
} catch {
    Write-Host "Could not set icon for Pizza Hut TV Pi Client, using default"
}

# Save the shortcut
$Shortcut.Save()

Write-Host "Desktop shortcut created: $ShortcutPath"
Write-Host "You can now double-click 'Pizza Hut TV Pi Client' on your desktop to launch!"

# Create EATV shortcut pointing to the same launcher
$ShortcutEATV = $WScriptShell.CreateShortcut($ShortcutPathEATV)
$ShortcutEATV.TargetPath = $TargetPath
$ShortcutEATV.WorkingDirectory = $WorkingDirectory
$ShortcutEATV.Description = "EATV - Launch the Pizza Hut TV experience"
$ShortcutEATV.WindowStyle = 1

try {
    $ShortcutEATV.IconLocation = "shell32.dll,18"  # Alternate monitor icon
} catch {
    Write-Host "Could not set icon for EATV shortcut, using default"
}

$ShortcutEATV.Save()

Write-Host "Desktop shortcut created: $ShortcutPathEATV"
Write-Host "Launch the software anytime by double-clicking 'EATV' on your desktop."

# Make the batch file executable (already is, but just in case)
if (Test-Path $TargetPath) {
    Write-Host "Launcher script ready: $TargetPath"
} else {
    Write-Host "Warning: Launcher script not found at $TargetPath"
}