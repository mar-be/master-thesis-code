from threading import Thread
from typing import List
from virtualization_layer import Virtualization_Layer
from qiskit import IBMQ
from quantum_job import QuantumTask, Status
from api.util import must_have
from flask import Flask, request, jsonify
from flask_restful import Resource, Api
from queue import Empty, Queue
import logger


class TaskDAO():

    def __init__(self) -> None:
        self._data = {}

    def get_task(self, id):
        return self._data.get(id)
 
    def add_task(self, task):
        self._data[task.id] = task
 
    def delete_task(self, id):
        if id not in self._data.keys():
            return None
        return self._data.pop(id)
        
 
    def update_task(self, task):
        self._data[task.id] = task    
    


class HelloWorld(Resource):
    def get(self):
        return {'hello': 'world'}


class Task_DAO_Resource(Resource):

    def __init__(self) -> None:
        must_have(self, member="task_dao", of_type=TaskDAO, use_method=Task_DAO_Resource.create.__name__)
        super().__init__()

    @classmethod
    def create(cls, task_dao):
        """creates a Task_DAO_Resource with the given TaskDAO

        Args:
            task_dao (TaskDAO): an instance of TaskDAO to access the tasks

        Returns:
            Task: class object of Task Resource
        """        
     
        cls.task_dao = task_dao
        return cls

class TaskCreation(Task_DAO_Resource):

    def __init__(self) -> None:
        super().__init__()

    def post(self):
        if request.is_json:
                body = request.get_json()
                if "circuits" in body.keys():
                    result_list = []
                    for item in body["circuits"]:
                        quantum_task = QuantumTask.create(item)
                        self.task_dao.add_task(quantum_task)
                        result_list.append({"id":quantum_task.id})
                    return jsonify(results=result_list)
                else:
                    quantum_task = QuantumTask.create(body)
                    self.task_dao.add_task(quantum_task)
                    return jsonify(id=quantum_task.id)
          

class Task(Task_DAO_Resource):

    def __init__(self) -> None:
        super().__init__()

    def get(self, task_id):
        task = self.task_dao.get_task(task_id)
        if task is None:
            return 'TaskDoesNotExist', 404
        return jsonify(**task.to_dict())

    def put(self, task_id):
        task = self.task_dao.get_task(task_id)
        if task is None:
            return 'TaskDoesNotExist', 404
        task.status = Status.running
        Task.run_queue.put(task)
        self.task_dao.update_task(task)
        return '', 202

    def delete(self, task_id):
        task = self.task_dao.delete_task(task_id)
        if task is None:
            return 'TaskDoesNotExist', 404
        latest_status = task.status
        return jsonify(latest_status=latest_status.name)

    
    @classmethod
    def set_run_queue(cls, run_queue:Queue) -> None:  
        """Sets the queue to run the tasks

        Args:
            run_queue (Queue): input queue of the virtualization layer
        """        
        cls.run_queue = run_queue


class APIResultUpdater(Thread):
    
    def __init__(self, tasks:Queue(), errors:Queue(), task_dao:TaskDAO) -> None:
        self._log = logger.get_logger(type(self).__name__)
        self._tasks = tasks
        self._errors = errors
        self._tasks_dao = task_dao
        Thread.__init__(self)

    
    def run(self) -> None:
        while True:
            while not self._errors.empty():
                try:
                    error_task = self._errors.get(block=False)
                    error_task.status = Status.failed
                    self._tasks_dao.update_task(error_task)
                except Empty:
                    break
            try:
                task = self._tasks.get(timeout=10)
                task.status = Status.done
                self._tasks_dao.update_task(task)
                self._log.info(f"Received result for task {task.id}")
            except Empty:
                continue
    

class API():

    def __init__(self, task_dao:TaskDAO, run_queue:Queue) -> None:
        self.app = Flask(__name__)
        self.api = Api(self.app)
        self.api.add_resource(HelloWorld, '/')
        TaskCreation_Init = TaskCreation.create(task_dao)
        self.api.add_resource(TaskCreation_Init, "/task")
        Task.set_run_queue(run_queue)
        Task_Init = Task.create(task_dao)
        self.api.add_resource(Task_Init, "/task/<string:task_id>")
        self.run_queue = run_queue

    def run(self, debug=False):
        self.app.run(debug=debug)





if __name__ == '__main__':
    provider = IBMQ.load_account()

    vl = Virtualization_Layer(provider)

   

    vl.start()
    task_dao = TaskDAO()
    api = API(task_dao, vl.input)
    result_updater = APIResultUpdater(vl.output, vl.errors, task_dao)
    result_updater.start()

    api.run(debug=True)
