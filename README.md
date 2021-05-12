# Bringing the Concepts of Virtualization to Gate-based Quantum Computing


## Installation
1. Make a virtual environment and install required packages:
```
conda create -n qc_virt python=3.8.5
conda deactivate && conda activate qc_virt
pip install numpy matplotlib pillow pydot termcolor
pip install qiskit==0.24.0
conda config --add channels http://conda.anaconda.org/gurobi
conda install gurobi
```
2. Set up a Gurobi license: https://www.gurobi.com.
3. Install Intel compiler:
Included in Intel oneAPI HPC Toolkit (https://software.intel.com/content/www/us/en/develop/tools/oneapi/hpc-toolkit.html)
1. Install Intel MKL(https://software.intel.com/content/www/us/en/develop/tools/oneapi/components/onemkl.html) 
Via anaconda:
```
conda install -c intel mkl
```
5. After installation, do (file location may vary depending on installation):
```
source /opt/intel/oneapi/setvars.sh intel64 
```

## Run

### As a service with API
1. Start a MongoDB. Here is a [Docker Compose File](api/docker-compose.yaml).
2. Configure the API to use the database in the following [file](api/__main__.py).
3. Run: ```python -m api```

### import locally 
