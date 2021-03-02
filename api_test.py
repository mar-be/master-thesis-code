from qiskit.circuit.random.utils import random_circuit
import requests
import json
import time

url_creation = "http://localhost:5000/task"
url_task = "http://localhost:5000/task/"

headers = {'Content-Type': 'application/json'}

tasks = []
circuits = []
for i in range(1):
    circuits.append({"qasm":random_circuit(16, 5, 2, measure=True).qasm(), "shots":8192})

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
    response = requests.request("GET", url_task+task)
    res_json= json.loads(response.text)
    if res_json["status"] == "running":
        print(f"{res_json['id']} is still running")
        time.sleep(10)
        continue
    tasks.pop(0)
    print(res_json)
