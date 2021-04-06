# Bringing the Concepts of Virtualization to Gate-based Quantum Computing

## CutQC
A Python package for CutQC

### Installation
1. Make a virtual environment and install required packages:
```
conda create -n artifact python=3.7
conda deactivate && conda activate artifact
pip install numpy matplotlib pillow pydot termcolor
pip install qiskit==0.24.0
conda config --add channels http://conda.anaconda.org/gurobi
conda install gurobi
```
2. Set up a Gurobi license: https://www.gurobi.com.
3. Install Intel compiler:
Included in Intel oneAPI HPC Toolkit (https://software.intel.com/content/www/us/en/develop/tools/oneapi/hpc-toolkit.html) for example
4. Install Intel MKL(https://software.intel.com/content/www/us/en/develop/tools/oneapi/components/onemkl.html): 
Via anaconda
```
conda install -c intel mkl
```
5. After installation, do (file location may vary depending on installation):
```
source /opt/intel/oneapi/setvars.sh intel64 
```