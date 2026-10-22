#!/bin/bash
#SBATCH --job-name=osa-env
#SBATCH --partition=short
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --output=/projects/scalable_design_participation_lab/open-sensing-built-env-counts-2026-09-17/logs/build_env-%j.out
#SBATCH --error=/projects/scalable_design_participation_lab/open-sensing-built-env-counts-2026-09-17/logs/build_env-%j.err

set -euo pipefail
RUN=/projects/scalable_design_participation_lab/open-sensing-built-env-counts-2026-09-17
UV_DIR=$RUN/src/uvbin
export UV_CACHE_DIR=$RUN/src/uvcache
export XDG_DATA_HOME=$RUN/src/uvdata

curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=$UV_DIR INSTALLER_NO_MODIFY_PATH=1 sh
UV=$UV_DIR/uv
echo "uv at: $UV"
$UV --version

rm -rf $RUN/venv
$UV venv --python 3.12 $RUN/venv
PY=$RUN/venv/bin/python
echo "python: $($PY --version)"

$UV pip install --python $PY \
  --index-url https://download.pytorch.org/whl/cpu \
  --extra-index-url https://pypi.org/simple \
  torch==2.6.0 torchvision==0.21.0

$UV pip install --python $PY \
  ultralytics==8.4.7 numpy==2.0.2 opencv-python==4.10.0.84 pillow==11.1.0 \
  matplotlib==3.10.1 requests pandas==2.2.3 tqdm osmnx geopandas==1.0.1 fiona

echo '=== versions ==='
$PY -c "
import sys, torch, ultralytics, numpy, cv2, PIL, matplotlib
print('python', sys.version.split()[0])
print('torch', torch.__version__)
print('ultralytics', ultralytics.__version__)
print('numpy', numpy.__version__)
print('opencv', cv2.__version__)
print('pillow', PIL.__version__)
print('cuda', torch.cuda.is_available())
"
echo 'ENV BUILD DONE'
