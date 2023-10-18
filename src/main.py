from flask import Flask
import logging
from werkzeug.exceptions import HTTPException
from werkzeug import serving
import pprint

from azure.core.messaging import CloudEvent
from flask import request, Blueprint, Response
from azure.eventgrid import EventGridEvent
from flask import request, Blueprint, Response, json

from azure.communication.callautomation._shared.models import identifier_from_raw_id

from events import EventsHandler


import config

app = Flask(__name__,
            static_folder='res'
            #static_url_path=AUDIO_FILES_PATH,
)


"""
This is controller where it will receive interim events from Call automation service.
We are utilizing event handler, this will handle events and relay to our business logic.
"""
@app.route('/api/event', methods=['POST'])
def event_handler():
    for event_dict in request.json:
        event = CloudEvent.from_dict(event_dict)

        caller_id = request.args.get('callerId', None).replace('4: ', '4:+')  # Is this a dumb bug ??
        if caller_id:
            initial_caller = identifier_from_raw_id(caller_id)
        else:
            initial_caller = None

        EventsHandler().handle_callback_events(event, initial_caller)

        return Response(status=200)


@app.route('/api/newCall', methods=['POST'])
def incoming_call_handler():
    for event_dict in request.json:
        event = EventGridEvent.from_dict(event_dict)
        event_handler_response = EventsHandler().handle_incoming_events(event)
        return Response(response=json.dumps(event_handler_response), status=200)

@app.route('/healthz', methods=['GET'])
def healthz():
    return 'OK, motherfucker'



if __name__ == "__main__":
    app.logger.setLevel(logging.DEBUG)
    app.run(port=8080, host='0.0.0.0', debug=True)

