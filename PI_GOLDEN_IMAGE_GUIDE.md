# Pizza Hut TV Golden Image Guide

This workflow is for creating a Raspberry Pi SD card image that needs no SSH and no terminal for end users.

## Goal

After the image is prepared and cloned, the user should only need to:

1. Insert SD card.
2. Connect power and internet.
3. Wait for the Pizza Hut TV claim screen.
4. Scan the QR code or enter the claim code in Pi Manager.
5. Finish store and screen assignment from the dashboard.

## What Makes This Work

The Pi client now shows a claim code screen automatically when both of these files are missing:

1. `~/.pizza_hut_tv_config.json`
2. `~/.pizza_hut_tv_id`

That means the golden image must contain the installed app and enabled service, but it must not contain a saved Pi ID or playback config.

## Prepare The Reference Pi

Flash Raspberry Pi OS onto one reference Pi and get it online.

From this repo on Windows, run:

```powershell
.\prepare_pi_golden_image.ps1 -PiUser everydayadvertise -PiHost everydayadvertise
```

That script will:

1. Copy the current client files to the Pi.
2. Install dependencies.
3. Install and enable the `pizza-hut-tv` systemd service.
4. Remove device-specific runtime files so the image stays unclaimed.

## Optional Live Test Before Cloning

If you want to confirm that the Pi boots into the claim screen before cloning the SD card:

```powershell
.\prepare_pi_golden_image.ps1 -PiUser everydayadvertise -PiHost everydayadvertise -StartNow
```

After testing, finalize the image again before cloning:

```powershell
.\prepare_pi_golden_image.ps1 -PiUser everydayadvertise -PiHost everydayadvertise -FinalizeImage
```

## Clone The SD Card

Once the image is finalized:

1. Shut down the reference Pi.
2. Clone the SD card with your normal imaging tool.
3. Use that cloned card in new Pis.

## End-User Experience

For each new Pi made from the golden image:

1. User inserts SD card.
2. User connects power and network.
3. The Pi boots directly into the claim code screen.
4. User opens Pi Manager.
5. User scans the QR code or enters the claim code.
6. User assigns store and screen.
7. The Pi saves config and reboots into normal playback behavior on every future start.

## Notes

1. The reference image should not be used as a live production device after finalization.
2. If `~/.pizza_hut_tv_id` exists when you clone the SD card, every cloned Pi will share the same Pi identity. Do not skip finalization.
3. If `~/.pizza_hut_tv_config.json` exists when you clone the SD card, every cloned Pi will inherit the same assignment. Do not skip finalization.