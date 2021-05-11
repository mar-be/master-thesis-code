from qiskit.circuit.random.utils import random_circuit
import requests
import json
import time

url_creation = "http://localhost:5000/tasks"
url_task = "http://localhost:5000/tasks/"

headers = {'Content-Type': 'application/json'}

tasks = []
circuits = []
for i in range(20):
    circuits.append({"qasm":random_circuit(5, 5, 2, measure=True).qasm(), "config":{ "quantum_resource_mapper": {"backend_chooser":{"allow_simulator":True}, "execution_types":{"aggregation":False}}}})

print("Send request")
response = requests.request("POST", url_creation, json={"circuits":circuits}, headers=headers)
print(response.text)
results = json.loads(response.text)

for res in results["results"]:
    tasks.append(res["id"])

for task in tasks:
    response = requests.request("PUT", url_task+task)
    print(f"Started {task}")


while len(tasks)>0:
    task = tasks[0]
    response = requests.request("GET", url_task+task+"/status")
    res_json = json.loads(response.text)
    if res_json["status"] == "running":
        print(f"{task} is still running")
        time.sleep(10)
        continue
    response = requests.request("GET", url_task+task+"/result")
    print(response.text)
    tasks.pop(0)
