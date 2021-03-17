from threading import Thread
from typing import Dict, Optional
from bson.objectid import ObjectId

from mongoengine.fields import DictField, IntField, StringField
from virtualization_layer import Virtualization_Layer
import ibmq_account
from quantum_job import QuantumJob
from flask import Flask, request, jsonify
import flask_restful
from queue import Empty, Queue
import logger
from flask_mongoengine import Document, MongoEngine, DynamicDocument
from qiskit import QuantumCircuit
import config.load_config as cfg

import logger

class Task(Document):
    qasm = StringField(required=True)
    shots = IntField(min_value=0)
    qjob_id = StringField(null=True)
    status = StringField(default="created")
    result_prob = DictField(null=True)
    result_cnts = DictField(null=True)

    @property
    def id_str(self):
        return str(self.id)

    def to_dict(self):
        d = {"id":self.id_str, "qasm":self.qasm, "status":self.status, "shots":self.shots}
        if self.result_prob:
            d["result_prob"] = self.result_prob
        if self.result_cnts:
            d["result_cnts"] = self.result_cnts
        return d

    def update_results(self, job:QuantumJob):
        self.result_prob = job.result_prob

    def create_qjob(self):
        qjob = QuantumJob(QuantumCircuit.from_qasm_str(self.qasm), shots=self.shots)
        self.qjob_id = qjob.id
        return qjob

class HelloWorld(flask_restful.Resource):
    def get(self):
        return {'hello': 'world'}


class TaskCreation_API(flask_restful.Resource):


    def post(self):
        if request.is_json:
                body = request.get_json()
                if "circuits" in body.keys():
                    result_list = []
                    for item in body["circuits"]:
                        task = Task(**item)
                        task.save()
                        result_list.append({"id":task.id_str})
                    return jsonify(results=result_list)
                else:
                    task = Task(**body)
                    task.save()
                    return jsonify(id=task.id_str)

def get_task(task_id:str) -> Optional[ObjectId]:
    o_id = ObjectId(task_id)
    return Task.objects(id=o_id).first()

class Task_API(flask_restful.Resource):


    def get(self, task_id):
        task = get_task(task_id)
        if task is None:
            return 'TaskDoesNotExist', 404
        return jsonify(**task.to_dict())

    def put(self, task_id):
        task = get_task(task_id)
        if task is None:
            return 'TaskDoesNotExist', 404
        task.status = "running"
        Task_API.run_queue.put(task.create_qjob())
        task.save()
        return '', 202

    def delete(self, task_id):
        task = get_task(task_id)
        if task is None:
            return 'TaskDoesNotExist', 404
        latest_status = task.status
        task.delete()
        return jsonify(latest_status=latest_status)

    
    @classmethod
    def set_run_queue(cls, run_queue:Queue) -> None:  
        """Sets the queue to run the tasks

        Args:
            run_queue (Queue): input queue of the virtualization layer
        """        
        cls.run_queue = run_queue


class APIResultUpdater(Thread):
    
    def __init__(self, tasks:Queue(), errors:Queue()) -> None:
        self._log = logger.get_logger(type(self).__name__)
        self._tasks = tasks
        self._errors = errors
        Thread.__init__(self)

    
    def run(self) -> None:
        while True:
            while not self._errors.empty():
                try:
                    error_job = self._errors.get(block=False)
                    error_task = Task.objects(qjob_id=error_job.id).first()
                    error_task.status = "failed"
                    error_task.save()
                except Empty:
                    break
            try:
                job = self._tasks.get(timeout=10)
                task = Task.objects(qjob_id=job.id).first()
                task.status = "done"
                #TODO copy results
                task.update_results(job)
                task.save()
                self._log.info(f"Received result for task {task.id}")
            except Empty:
                continue
    

class API():

    def __init__(self, run_queue:Queue, mongo_config:Dict) -> None:
        self.app = Flask(__name__)
        self.api = flask_restful.Api(self.app)
        self.api.add_resource(HelloWorld, '/')
        self.api.add_resource(TaskCreation_API, "/task")
        Task_API.set_run_queue(run_queue)
        self.api.add_resource(Task_API, "/task/<string:task_id>")
        self.run_queue = run_queue
        self.app.config['MONGODB_SETTINGS'] = mongo_config
        self.db = MongoEngine(self.app)

    def run(self, debug=False):
        self.app.run(debug=debug)


# Class-based application configuration
class ConfigClass(object):
    """ Flask application config """

    # Flask settings
    SECRET_KEY = 'This is an INSECURE secret!! DO NOT use this in production!!'

    # Flask-MongoEngine settings
    MONGODB_SETTINGS = {
            'alias': 'default',
            'db': "tasks",
            'host': "localhost",
            'port': 27017,
            'username': "root",
            'password': "rootpassword",
            "authentication_source": "admin"
        }


def initialize_routes(api):
    api.add_resource(HelloWorld, '/')
    api.add_resource(TaskCreation_API, "/task")
    api.add_resource(Task_API, "/task/<string:task_id>")


def create_app():
    """ Flask application factory """

    # Setup Flask and load app.config
    app = Flask(__name__)
    app.config.from_object(__name__+'.ConfigClass')
    api = flask_restful.Api(app)


    MongoEngine(app)

    initialize_routes(api)

    return app



if __name__ == '__main__':

    config = cfg.load_or_create()
    logger.set_log_level(config)
    provider = ibmq_account.get_provider(config)

    vl = Virtualization_Layer(provider)
    vl.start()

    Task_API.set_run_queue(vl.input)


    result_updater = APIResultUpdater(vl.output, vl.errors)
    result_updater.start()

    app = create_app()

    app.run(debug=True)
