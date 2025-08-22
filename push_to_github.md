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

## Troubleshooting
- If authentication fails, use GitHub Desktop app
- Or set up Personal Access Token in GitHub settings

## How to Make an Existing Repository Private
If your repository is currently public and you want to make it private:

1. Go to your repository on GitHub: https://github.com/pheng81/pizza-hut-tv
2. Click "Settings" tab (requires owner/admin access)
3. Scroll down to the "Danger Zone" section at the bottom
4. Click "Change repository visibility"
5. Select "Make private"
6. Type the repository name to confirm
7. Click "I understand, change repository visibility"

**Important Notes:**
- Only repository owners can change visibility settings
- Making a repository private will restrict access to invited collaborators only
- Any public forks will become detached from the private repository
- Vercel deployments may need to be reconfigured if using GitHub integration
