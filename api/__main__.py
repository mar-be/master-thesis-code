from api.db_models import Task
import config.load_config as cfg
import flask_restful
import ibmq_account
import logger
from flask import Flask
from flask_mongoengine import MongoEngine
from virtualization_layer import Virtual_Execution_Environment

from api.resources import HelloWorld, Task_API, TaskCreation_API, Task_Result, Task_Status
from api.results import ResultFetcher


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


def _initialize_routes(api):
    api.add_resource(HelloWorld, '/')
    api.add_resource(TaskCreation_API, "/tasks")
    api.add_resource(Task_API, "/tasks/<string:task_id>")
    api.add_resource(Task_Status, "/tasks/<string:task_id>/status")
    api.add_resource(Task_Result, "/tasks/<string:task_id>/result")



def create_app():
    """ Flask application factory """

    # Setup Flask and load app.config
    app = Flask(__name__)
    app.config.from_object(__name__+'.ConfigClass')
    api = flask_restful.Api(app)


    MongoEngine(app)

    _initialize_routes(api)

    return app



if __name__ == '__main__':

    config = cfg.load_or_create()
    logger.set_log_level_from_config(config)
    provider = ibmq_account.get_provider(config)

    vee = Virtual_Execution_Environment(provider, config)
    vee.start()

    Task_API.set_run_queue(vee.input)


    result_updater = ResultFetcher(vee.output, vee.errors)
    result_updater.start()

    app = create_app()

    app.run(debug=True)
