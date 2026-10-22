#!/bin/bash
#SBATCH --job-name=osa-merge
#SBATCH --partition=short
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --output=/projects/scalable_design_participation_lab/open-sensing-built-env-counts-2026-09-17/logs/merge-%j.out
#SBATCH --error=/projects/scalable_design_participation_lab/open-sensing-built-env-counts-2026-09-17/logs/merge-%j.err

set -euo pipefail
cd /projects/scalable_design_participation_lab/open-sensing-built-env-counts-2026-09-17/src
export MPLCONFIGDIR=/projects/scalable_design_participation_lab/open-sensing-built-env-counts-2026-09-17/src/mpl_config
/projects/scalable_design_participation_lab/open-sensing-built-env-counts-2026-09-17/venv/bin/python merge.py
