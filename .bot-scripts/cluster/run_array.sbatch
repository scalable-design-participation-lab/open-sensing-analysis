#!/bin/bash
#SBATCH --job-name=osa-feat
#SBATCH --partition=short
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=12G
#SBATCH --time=04:00:00
#SBATCH --output=/projects/scalable_design_participation_lab/open-sensing-built-env-counts-2026-09-17/logs/feat-%A_%a.out
#SBATCH --error=/projects/scalable_design_participation_lab/open-sensing-built-env-counts-2026-09-17/logs/feat-%A_%a.err

set -euo pipefail
cd /projects/scalable_design_participation_lab/open-sensing-built-env-counts-2026-09-17/src
export YOLO_CONFIG_DIR=/projects/scalable_design_participation_lab/open-sensing-built-env-counts-2026-09-17/src/ultralytics_config
export MPLCONFIGDIR=/projects/scalable_design_participation_lab/open-sensing-built-env-counts-2026-09-17/src/mpl_config
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK
/projects/scalable_design_participation_lab/open-sensing-built-env-counts-2026-09-17/venv/bin/python run_slice.py $SLURM_ARRAY_TASK_ID
