# Repository Privacy Setup Guide

## Making Your Repository Private

### For New Repositories
When creating a new repository on GitHub:
1. Select "Private" instead of "Public" during repository creation
2. This ensures your code is only visible to you and invited collaborators

### For Existing Repositories (Current Setup)
To change an existing public repository to private:

1. **Go to Repository Settings**
   - Navigate to https://github.com/pheng81/pizza-hut-tv
   - Click the "Settings" tab (you must be the repository owner)

2. **Change Visibility**
   - Scroll down to the "Danger Zone" section
   - Click "Change repository visibility"
   - Select "Make private"

3. **Confirm the Change**
   - Type the repository name exactly: `pizza-hut-tv`
   - Click "I understand, change repository visibility"

## Important Considerations

### Access Control
- Private repositories are only accessible to:
  - The repository owner (you)
  - Explicitly invited collaborators
  - Organization members (if applicable)

### Deployment Impact
- **Vercel**: May need to reconnect GitHub integration
- **Other CI/CD**: Check if deployment services need updated permissions

### Collaborators
To add collaborators to a private repository:
1. Go to Settings > Manage access
2. Click "Invite a collaborator"
3. Enter GitHub username or email
4. Select permission level (Read, Write, or Admin)

### Security Benefits
- Source code is not publicly searchable
- API keys and configuration details are protected
- Business logic remains confidential
- Reduces risk of unauthorized forks

## Verification Steps
After making the repository private:
1. Sign out of GitHub or use incognito mode
2. Try to access https://github.com/pheng81/pizza-hut-tv
3. You should see a "404 - Not Found" error, confirming privacy

## Alternative: Organization Repository
Consider moving the repository to a GitHub Organization for better team management:
1. Create a GitHub Organization
2. Transfer the repository to the organization
3. Set organization-level privacy policies
4. Manage team access more efficiently