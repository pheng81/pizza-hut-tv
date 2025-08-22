# GitHub Repository Setup for Pizza Hut TV

## Step 1: Create Repository on GitHub
1. Go to https://github.com/pheng81
2. Click "New repository" (green button)
3. Repository name: **pizza-hut-tv**
4. Set to **Private** (recommended for business applications)
5. **Don't** check "Initialize with README"
6. Click "Create repository"

## Step 2: Push Code to GitHub
After creating the repository, run these commands:

```powershell
cd "c:\Users\toeng\Pizza Hut TV"

# Configure git user (if not done before)
git config user.name "pheng81"
git config user.email "your-email@example.com"

# Add remote repository
git remote add origin https://github.com/pheng81/pizza-hut-tv.git

# Push to GitHub
git push -u origin main
```

## Step 3: Deploy on Vercel
1. Go to https://vercel.com (login as pizzahut_display)
2. Click "New Project"
3. Import from GitHub: pheng81/pizza-hut-tv
4. Click "Deploy"

## Step 4: Change Existing Repository to Private (If Already Public)
If your repository is currently public and you want to make it private:

1. Go to https://github.com/pheng81/pizza-hut-tv
2. Click on "Settings" tab (top of the repository page)
3. Scroll down to the "Danger Zone" section at the bottom
4. Click "Change repository visibility"
5. Select "Make private"
6. Type the repository name `pheng81/pizza-hut-tv` to confirm
7. Click "I understand, change repository visibility"

**Note:** Making the repository private means:
- Only you and collaborators you invite can see the repository
- The repository won't appear in search results
- Vercel deployments will still work with private repositories
- You may need to reconnect Vercel if you haven't already granted private repository access

## Troubleshooting
- If authentication fails, use GitHub Desktop app
- Or set up Personal Access Token in GitHub settings
