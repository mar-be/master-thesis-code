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
3. Customize the ```config.json``` in the root directory (If it is not present, it will be generated at the first startup)
4. Run: ```python -m api```
5. Send requests to http://localhost:5000

### import locally 
Import the [Virtual_Execution_Environment](virtualization.py) and initialize it as following:

```
import config.load_config as cfg
import ibmq_account
from virtualization import Virtual_Execution_Environment

config = cfg.load_or_create()
provider = ibmq_account.get_provider(config)

vee = Virtual_Execution_Environment(provider, config)
vee.start()

input_queue = vee.input
output_queue = vee.output
error_queue = vee.errors
```

## Evaluation
### RB for Aggregation
Randomized benchmarking of the QPUs with the aggregated quantum circuits: [randomized_benchmarking.py](randomized_benchmarking.py) \
Evaluation of the randomized benchmarking results and their visualization: [read_rb_files.py](read_rb_files.py)

### Evaluation of aggregated quantum circuits
Generate evaluation data for different aggregated quantum circuits: [eval_agg_circuits.py](eval_agg_circuits.py) \
Evaluation of the results and their visualization: [read_eval_files_circ.py](read_eval_files_circ.py)

### Evaluation of Partitioning
Generate evaluation data for one partitioned quantum circuit with one specific cut: [eval_partition_pipeline.py](eval_partition_pipeline.py) \
Generate evaluation data for different partitioned quantum circuit with various cuts: [eval_part_circuits.py](eval_part_circuits.py) \
Evaluation of the results and their visualization: [read_eval_files_circ.py](read_eval_files_circ.py)

## License
The self-produced code is available under the [Apache-2.0 License](LICENSE).

This project includes parts from third party libraries.
Their use is subject to their license terms.
The following third party libraries were used:

1. Tang, Wei. (2020). CutQC: Using Small Quantum Computers for Large Quantum Circuit Evaluations. Presented at the Architectural Support for Programming Languages and Operating Systems (ASPLOS), Zenodo. http://doi.org/10.5281/zenodo.4329804 \
The library is licensed under the [Creative Commons Attribution 4.0 International License](http://creativecommons.org/licenses/by/4.0/) \
The following directories include parts of the library: [cutqc](cutqc) and [qiskit_helper_functions](qiskit_helper_functions)

2. [quantum-circuit-generator](https://github.com/teaguetomesh/quantum_circuit_generator) Copyright (c) 2021 Teague Tomesh \
The library is licensed under the [MIT License](quantum_circuit_generator/LICENSE) \
The following directory includes the library: [quantum_circuit_generator](quantum_circuit_generator)