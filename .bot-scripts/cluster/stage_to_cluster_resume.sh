set -u
RUN=/projects/scalable_design_participation_lab/open-sensing-built-env-counts-2026-09-17
D=/Users/legariapena.j/Documents/open-sensing-analysis/open-sensing-analysis/data/2026_09_16_site_built_environment_comparison
for i in $(seq 1 40); do
  N=$(ssh -o BatchMode=yes explorer "find $RUN/data/sites -name '*.jpg' | wc -l" 2>/dev/null | tr -d ' ')
  echo "pass $i start: $N / 9250"
  if [ "$N" = "9250" ]; then echo "ALL IMAGES PRESENT"; break; fi
  rsync -a --partial --inplace --timeout=180 \
    --exclude='feature_maps/' --exclude='*.png' --exclude='.DS_Store' \
    -e "ssh -o BatchMode=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=6 -o TCPKeepAlive=yes" \
    "$D/" explorer:"$RUN/data/sites/" && echo "pass $i rsync returned clean" || echo "pass $i rsync dropped"
done
FINAL=$(ssh -o BatchMode=yes explorer "find $RUN/data/sites -name '*.jpg' | wc -l" 2>/dev/null | tr -d ' ')
ZERO=$(ssh -o BatchMode=yes explorer "find $RUN/data/sites -name '*.jpg' -size 0 | wc -l" 2>/dev/null | tr -d ' ')
echo "FINAL COUNT: $FINAL / 9250 ; zero-byte: $ZERO"
[ "$FINAL" = "9250" ] && echo "STAGING VERIFIED" || echo "STAGING INCOMPLETE"
