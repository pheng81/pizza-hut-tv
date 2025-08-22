# Quick Upload Guide for Pizza Hut TV

## Method 1: Manual Upload (Recommended)
1. Go to: https://github.com/pheng81/pizza-hut-tv
2. Click "Add file" → "Upload files"
3. Select and drag ALL files from: c:\Users\toeng\Pizza Hut TV\
4. Write commit message: "Initial upload - Pizza Hut TV Dashboard"
5. Click "Commit changes"

## Method 2: GitHub Desktop
1. Download: https://desktop.github.com/
2. Sign in with pheng81 account
3. Clone repository
4. Copy files to cloned folder
5. Commit and push

## Files to Upload (Important):
✅ app.py (main Flask app)
✅ requirements.txt (dependencies)
✅ vercel.json (Vercel config)
✅ api/index.py (entry point)
✅ templates/ folder (HTML files)
✅ static/ folder (CSS, JS, images)
✅ store_config.json (configuration)
✅ All other project files

## After Upload:
1. Go to vercel.com (login as pizzahut_display)
2. Import pheng81/pizza-hut-tv
3. Deploy with settings:
   - Framework: Other
   - Root Directory: ./
   - Build/Output Commands: (empty)
4. Get your live URL: pizza-hut-tv.vercel.app

## Making Repository Private:
For business applications, it's recommended to make your repository private:
1. Go to repository Settings → Scroll to "Danger Zone"
2. Click "Change repository visibility" → "Make private"
3. Confirm by typing the repository name
4. Vercel will continue to work with private repositories
