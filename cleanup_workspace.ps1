# Workspace Cleanup Script
# Safely removes temporary, debug, test, and duplicate files

$ErrorActionPreference = "Continue"
$deleted = @()

Write-Host "Starting workspace cleanup..." -ForegroundColor Cyan
Write-Host ""

# Track statistics
$stats = @{
    "Check Scripts" = 0
    "Debug/Test Scripts" = 0
    "Duplicate Databases" = 0
    "Backup Configs" = 0
    "Backup Python" = 0
    "Log Files" = 0
    "Test Media" = 0
    "Old Scripts" = 0
    "Shell Scripts" = 0
    "Archives" = 0
    "Test HTML" = 0
    "JSON Test Files" = 0
}

# Files to delete
$filesToDelete = @(
    # Check scripts (36 files)
    "check_*.py",
    
    # Debug and test scripts
    "debug_*.py",
    "test_*.py",
    "diagnose_*.py",
    "analyze_*.py",
    "verify_*.py",
    "compare_*.py",
    "explain_*.py",
    
    # Add/Remove/Fix/Get scripts
    "add_item*.py",
    "add_sync*.py",
    "add_test*.py",
    "add_mom*.py",
    "add_image*.py",
    "find_*.py",
    "get_*.py",
    "list_*.py",
    "manual_*.py",
    "pair_*.py",
    "remove_*.py",
    "fix_*.py",
    "create_test*.py",
    "create_local*.py",
    "create_mom*.py",
    "create_empty*.py",
    "integrate_*.py",
    "crop_*.py",
    "update_test*.py",
    "update_pi_*.py",
    
    # Duplicate databases
    "database_backup.db",
    "database_from_server.db",
    "pizzahut.db",
    "pizzahut_tv.db",
    "pizza_hut.db",
    "pizza_hut_tv.db",
    "users.db",
    "user_database.db",
    "users.sqlite",
    "users_from_server.sqlite",
    
    # Backup configs
    "pi1_config.json",
    "temp_pi1_config.json",
    "store_config_BACKUP_from_server.json",
    "RECOVERED_store_config.json",
    
    # Backup Python
    "app_backup_6_11.py",
    "app_from_git.py",
    "app_local_dev.py",
    
    # Logs
    "log_5564.txt",
    "log_5566.txt",
    "startup_log.txt",
    "pi_client_debug.log",
    
    # Test media
    "phtv_5564.xml",
    "phtv_5566.xml",
    "android_tv_screenshot.png",
    "current_pi_ui.png",
    "updated_pi_ui.png",
    "emulator_screen.png",
    
    # Old scripts
    "deploy.ps1",
    "simple_launcher.sh",
    "launch_pizza_hut_tv.sh",
    "launch_pi_client.bat",
    "start_player.sh",
    "pi_config_tool.py",
    "my_file_server.py",
    "media_player.py",
    "custom_player.py",
    "seamless_video_player.py",
    "standalone_player.py",
    "mpv_slice_player.py",
    "slice_kiosk.py",
    "pi_optimized_kiosk.py",
    "enhanced_pi_client.py",
    "enhanced_test_pi.py",
    "fixed_pi_client.py",
    "simple_debug_client.py",
    "phtv_pi_client.py",
    "pizza_hut_tv.py",
    "webplayer_style_pi_client.pi.py",
    "webplayer_style_pi_client.py",
    "pi_webplayer_client.py",
    "server_bootstrap.py",
    "enterprise_launcher.py",
    
    # Test HTML
    "rotation_debug.html",
    "rotation_test.html",
    "ea-logo-intro.html",
    "ea-logo-intro-updated.html",
    "ea-logo-intro-centered.html",
    
    # JSON test files
    "playlist_api.json",
    "playlist_response.json",
    "pi_id_ip_map.json",
    
    # Shell scripts
    "check_loop_behavior.ps1",
    "check_pi_status.ps1",
    "check_vnc_server_logs.ps1",
    "diagnose_schedule_filter.ps1",
    "restart_pi_fix.ps1",
    "restart_pi_service.ps1",
    "get_pi_id.ps1",
    "upload_dashboard.ps1",
    "upload_direct.ps1",
    "watch_server_logs.ps1",
    "quick_deploy_preview.ps1",
    "deploy_dashboard_only.ps1",
    "deploy_screen_preview.ps1",
    "deploy_server_only.ps1",
    "hard_restart_service.sh",
    "disable_pi_autostart.sh",
    "enable_pi_autostart.sh",
    "fix_webplayer_sync.sh",
    "install_custom_player.sh",
    "install_enhanced_pi.sh",
    "install_new_pi.sh",
    "install_pi_client.sh",
    "install_tailscale_pi.sh",
    "install_tailscale_server.sh",
    "integrate_vnc_pi.sh",
    "launch_setup_flow.sh",
    "setup_new_pi.sh",
    "setup_oauth.sh",
    "setup_pi_service.sh",
    "start_pi_with_vnc.sh",
    "update_pi_public_ip.sh",
    "deploy_complete_pi_client.sh",
    "deploy_enterprise_pi.sh",
    "deploy_pi_public_ip.sh",
    "deploy_and_test.sh",
    "deploy_fixes.ps1",
    "deploy_vnc_fix.ps1",
    "emergency_upload.sh",
    "emergency_uploader.py",
    "emergency_upload_endpoint.py",
    "emergency_deploy.py",
    
    # Archives
    "pi_client_working.tar.gz",
    "scripts.zip",
    "android_tv_app_working _syn_app.zip"
)

# Process each pattern
$totalDeleted = 0

foreach ($pattern in $filesToDelete) {
    $files = Get-ChildItem -Filter $pattern -ErrorAction SilentlyContinue
    foreach ($file in $files) {
        try {
            Remove-Item $file.FullName -Force
            Write-Host "  Deleted: $($file.Name)" -ForegroundColor Green
            $totalDeleted++
            
            # Categorize for stats
            if ($file.Name -like "check_*") { $stats["Check Scripts"]++ }
            elseif ($file.Name -like "*.db" -or $file.Name -like "*.sqlite") { $stats["Duplicate Databases"]++ }
            elseif ($file.Name -like "*backup*.py" -or $file.Name -like "*_from_git.py") { $stats["Backup Python"]++ }
            elseif ($file.Name -like "*BACKUP*.json" -or $file.Name -like "temp_*.json") { $stats["Backup Configs"]++ }
            elseif ($file.Name -like "*.log" -or $file.Name -like "log_*.txt") { $stats["Log Files"]++ }
            elseif ($file.Name -like "*.png" -or $file.Name -like "*.xml") { $stats["Test Media"]++ }
            elseif ($file.Name -like "*.html") { $stats["Test HTML"]++ }
            elseif ($file.Name -like "*.json") { $stats["JSON Test Files"]++ }
            elseif ($file.Name -like "*.ps1" -or $file.Name -like "*.sh") { $stats["Shell Scripts"]++ }
            elseif ($file.Name -like "*.tar.gz" -or $file.Name -like "*.zip") { $stats["Archives"]++ }
            elseif ($file.Name -like "debug_*" -or $file.Name -like "test_*" -or $file.Name -like "add_*" -or $file.Name -like "fix_*") { $stats["Debug/Test Scripts"]++ }
            else { $stats["Old Scripts"]++ }
            
        } catch {
            Write-Host "  Failed: $($file.Name) - $($_.Exception.Message)" -ForegroundColor Red
        }
    }
}

# Summary
Write-Host ""
Write-Host "============================================" -ForegroundColor Yellow
Write-Host "CLEANUP SUMMARY" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Yellow
Write-Host ""

foreach ($key in $stats.Keys | Sort-Object) {
    if ($stats[$key] -gt 0) {
        Write-Host "  $key : $($stats[$key]) files" -ForegroundColor Cyan
    }
}

Write-Host ""
Write-Host "Total files deleted: $totalDeleted" -ForegroundColor Green
Write-Host ""
Write-Host "Core system files preserved:" -ForegroundColor Green
Write-Host "  - app.py" -ForegroundColor DarkGreen
Write-Host "  - requirements.txt" -ForegroundColor DarkGreen
Write-Host "  - deploy_to_server.ps1" -ForegroundColor DarkGreen
Write-Host "  - deploy_pi_client.ps1" -ForegroundColor DarkGreen
Write-Host "  - complete_pi_client.py" -ForegroundColor DarkGreen
Write-Host "  - database.db" -ForegroundColor DarkGreen
Write-Host ""
Write-Host "Workspace cleanup complete!" -ForegroundColor Green
Write-Host ""
