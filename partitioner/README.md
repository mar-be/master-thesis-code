# CutQC
A Python package for CutQC

## Installation
1. Make a virtual environment and install required packages:
```
conda create -n artifact python=3.7
conda deactivate && conda activate artifact
pip install numpy qiskit matplotlib pillow pydot termcolor
conda config --add channels http://conda.anaconda.org/gurobi
conda install gurobi
```
2. Set up a Gurobi license: https://www.gurobi.com.
3. Install Intel MKL: https://software.intel.com/content/www/us/en/develop/tools/oneapi/components/onemkl.html. After installation, do (file location may vary depending on installation):
```
source /opt/intel/bin/compilervars.sh intel64
```