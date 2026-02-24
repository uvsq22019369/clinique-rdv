# Dans ton terminal local
echo "FORCE REBUILD $(date)" > .nocache
git add .nocache
git commit -m "Forcer le rebuild cache"
git push