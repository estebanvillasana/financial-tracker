# Git Guide for Financial Tracker

This guide contains simple Git commands to help you manage versions of your Financial Tracker application.

## Basic Git Commands

### Check Status
To see what files have been changed:
```
git status
```

### Save a Snapshot (Commit)
To save the current state of your project:
```
git add .
git commit -m "Description of changes"
```

### View History
To see all your saved snapshots:
```
git log
```
For a simpler view:
```
git log --oneline
```

### Go Back to a Previous Version
To go back to a specific commit (replace COMMIT_ID with the actual commit ID from git log):
```
git checkout COMMIT_ID
```

To go back to the latest version after checking out an old version:
```
git checkout main
```

### Create a Named Snapshot (Branch)
To create a new branch for trying out changes:
```
git branch branch_name
git checkout branch_name
```
Or in one command:
```
git checkout -b branch_name
```

### Switch Between Versions (Branches)
To switch to a different branch:
```
git checkout branch_name
```

### Merge Changes from Another Branch
To bring changes from another branch into your current branch:
```
git merge branch_name
```

## Recommended Workflow

1. Before making significant changes, create a commit:
   ```
   git add .
   git commit -m "Working version before changes"
   ```

2. Make your changes to the code

3. If you like the changes, save them:
   ```
   git add .
   git commit -m "Description of what you changed"
   ```

4. If you don't like the changes and want to go back:
   ```
   git reset --hard HEAD~1
   ```
   (This goes back one commit)

## Important Notes

- The database file (financial_tracker.db) is not tracked by Git because it's in the .gitignore file
- If you want to backup your database, you should copy it manually
- Always commit your changes before making significant modifications
