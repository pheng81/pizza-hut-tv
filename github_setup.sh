# Pizza Hut TV - GitHub Repository Setup Script
# This script initializes a git repository and pushes to GitHub
# Note: Repository should be set to PRIVATE for business applications

# Initialize git repository
git init

# Add all files
git add .

# Commit the changes
git commit -m "Pizza Hut TV Dashboard - Initial deployment"

# Add remote repository (replace with your GitHub repo URL)
# Make sure the repository is set to PRIVATE in GitHub settings
git remote add origin https://github.com/yourusername/pizza-hut-tv.git

# Push to GitHub
git push -u origin main

# After pushing, verify repository privacy settings:
# 1. Go to your repository on GitHub
# 2. Click Settings > General
# 3. Scroll to "Danger Zone" 
# 4. Ensure repository visibility is set to "Private"
