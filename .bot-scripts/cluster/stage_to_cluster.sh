set -u
RUN=/projects/scalable_design_participation_lab/open-sensing-built-env-counts-2026-09-17
D=/Users/legariapena.j/Documents/open-sensing-analysis/open-sensing-analysis/data/2026_09_16_site_built_environment_comparison
for i in $(seq 1 12); do
  rsync -a --partial --inplace --timeout=180 \
    --exclude='feature_maps/' --exclude='*.png' --exclude='.DS_Store' \
    -e "ssh -o BatchMode=yes -o ServerAliveInterval=20" \
    "$D/" explorer:"$RUN/data/sites/" && { echo "RSYNC COMPLETE on attempt $i"; break; }
  echo "attempt $i dropped, retrying"
done
echo "--- remote counts ---"
ssh -o BatchMode=yes explorer "find $RUN/data/sites -name '*.jpg' | wc -l; find $RUN/data/sites -name '*.jpg' -size 0 | wc -l; du -sh $RUN/data/sites"
