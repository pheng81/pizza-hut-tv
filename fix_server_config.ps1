# Fix screen mixup on server
$KeyPath = "C:\Users\toeng\.ssh\LightsailDefaultKey-ap-southeast-2.pem"
$Server = "54.252.90.27"

Write-Host "Uploading fix script to server..."
& scp -i $KeyPath "fix_screen_mixup.py" "ubuntu@${Server}:~/fix_screen_mixup.py"

Write-Host "`nRunning fix script on server..."
& ssh -i $KeyPath "ubuntu@${Server}" "cd /var/www/everydayadvertise_tv && python3 ~/fix_screen_mixup.py store_config__test9_at_gmail.com.json"

Write-Host "`nDone! Config fixed on server."
