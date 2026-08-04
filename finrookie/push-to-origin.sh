#!/bin/bash
# Push master 到 GitHub

echo "================================"
echo "Pushing master to origin..."
echo "================================"

# 显示待推送的提交
echo ""
echo "Commits to push:"
git log --oneline origin/master..HEAD

echo ""
echo "Running: git push origin master"
git push origin master

if [ $? -eq 0 ]; then
  echo ""
  echo "✅ Push successful!"
  echo ""
  git log --oneline -5
else
  echo ""
  echo "❌ Push failed. Check:"
  echo "  1. Network connectivity to github.com"
  echo "  2. GitHub credentials/SSH key"
  echo "  3. Repository access permission"
fi
