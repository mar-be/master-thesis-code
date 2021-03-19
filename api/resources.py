from queue import Queue
from typing import Optional

import flask_restful
from bson.objectid import ObjectId
from flask import jsonify, request

import api.db_models


def get_task(task_id:str) -> Optional[ObjectId]:
    o_id = ObjectId(task_id)
    return api.db_models.Task.objects(id=o_id).first()

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
                        task = api.db_models.Task(**item)
                        task.save()
                        result_list.append({"id":task.id_str})
                    return jsonify(results=result_list)
                else:
                    task = api.db_models.Task(**body)
                    task.save()
                    return jsonify(id=task.id_str)

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

class Task_Status(flask_restful.Resource):

    def get(self, task_id):
        task = get_task(task_id)
        if task is None:
            return 'TaskDoesNotExist', 404
        return jsonify(status=task.status)

class Task_Result(flask_restful.Resource):

    def get(self, task_id):
        task = get_task(task_id)
        if task is None:
            return 'TaskDoesNotExist', 404
        return jsonify(task.result)