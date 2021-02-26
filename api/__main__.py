from quantum_job import QuantumJob
from api.util import must_have
from flask import Flask, request
from flask_restful import Resource, Api

app = Flask(__name__)
api = Api(app)


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
        self._data.pop(id)
        return id
 
    def update_task(self, task):
        self.data[task.id] = task    
    


class HelloWorld(Resource):
    def get(self):
        return {'hello': 'world'}


class Task_DAO_Resource(Resource):

    def __init__(self) -> None:
        must_have(self, member="task_dao", of_type=TaskDAO, use_method=Task_DAO_Resource.create.__name__)
        super().__init__()

    @classmethod
    def create(cls, task_dao):
        """[summary]

        Args:
            task_dao (TaskDAO): an instance of ITodoRepository

        Returns:
            Task: class object of Task Resource
        """        
     
        cls.task_dao = task_dao
        return cls

class TaskCreation(Task_DAO_Resource):

    def post(self):
        if request.is_json:
                body = request.get_json()
                quantum_task = QuantumJob.create(body)
                self.task_dao.add_task(quantum_task)
                return quantum_task.id
          

class Task(Task_DAO_Resource):

    def get(self, task_id):
        return str(self.task_dao.get_task(task_id))

    

    



if __name__ == '__main__':
    api.add_resource(HelloWorld, '/')
    task_dao = TaskDAO()
    TaskCreation_Init = TaskCreation.create(task_dao)
    api.add_resource(TaskCreation_Init, "/task")
    Task_Init = Task.create(task_dao)
    api.add_resource(Task, "/task/<string:task_id>")
    app.run(debug=True) 