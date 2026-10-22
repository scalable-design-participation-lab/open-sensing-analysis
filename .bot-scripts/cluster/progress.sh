#!/bin/bash
RUN=/projects/scalable_design_participation_lab/open-sensing-built-env-counts-2026-09-17
echo "=== queue ==="
squeue -u $USER -o '%.12i %.10P %.10j %.8T %.10M %.5D %R' 2>/dev/null
TOTAL=$(python3 -c "import json;print(len(json.load(open('$RUN/data/slices.json'))))" 2>/dev/null || echo "?")
DONE=$(ls $RUN/data/slices/*.json 2>/dev/null | wc -l | tr -d ' ')
echo "=== slices: $DONE / $TOTAL ==="
echo "=== observed rate (s/point, last 10 finished tasks) ==="
grep -h "s/point" $RUN/logs/feat-*.out 2>/dev/null | tail -10
echo "=== failed tasks ==="
sacct -n -X --format=JobID,State -j $(squeue -u $USER -h -o '%A' | head -1) 2>/dev/null | grep -Ev "COMPLETED|RUNNING|PENDING" | head -10
echo "=== non-empty error logs ==="
find $RUN/logs -name "feat-*.err" -size +0 2>/dev/null | head -10
