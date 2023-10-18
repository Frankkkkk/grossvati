import logging
import time

from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.communication.callautomation import (
    CallAutomationClient,
    CallConnectionClient,
    PhoneNumberIdentifier,
    CallRejectReason,
    RecognitionChoice,
)
from azure.communication.callautomation import FileSource, TextSource

import config
import enums
import fsm

cac = CallAutomationClient.from_connection_string(config.ACS_CONNECTION_STRING)


fsms: dict[str, fsm.Call] = {}

def incoming_call(event):
    number = event.data['from']['rawId']
    if number == config.Grossvati_Number.raw_id or number == config.Frank_Number.raw_id:
        # Only answer calls from Grossvati's number
        logging.info(f'Will answer call from {number}')
        answer_call(event)
    else:
        logging.error(f'Will decline incoming call from {number}')
        decline_call(event)

def answer_call(event):
    try:
        logging.info(f"Answering call {event.data}")
        caller_id = event.data["from"]["rawId"]
        incoming_call_context = event.data['incomingCallContext']

        # Creating and setting up callback endpoint mid-call events
        event_callback_uri = config.WEBSERVICE_URL + "api/event?callerId=" + caller_id

        call_connection_properties = cac.answer_call(
            incoming_call_context, event_callback_uri,
            cognitive_services_endpoint=config.COG_SERV_ENDPOINT)
        return call_connection_properties

    except AzureError as ae:
        logging.error("Exception raised while answering call, %s", str(ae))
        raise

def decline_call(event):
    try:
        logging.info(f"Declining call {event.data}")
        incoming_call_context = event.data['incomingCallContext']

        cac.reject_call(incoming_call_context, call_reject_reason=CallRejectReason.FORBIDDEN)

    except AzureError as ae:
        logging.error("Exception raised while answering call, %s", str(ae))
        raise


def handle_event(event, call_connection_id, initial_caller):
    if call_connection_id not in fsms:
        fsms[call_connection_id] = fsm.Call(call_connection_id, initial_caller)

    c = fsms[call_connection_id]

    event_type = event.type

    print(f'\n\n\nNEW EVENT: {event_type}')
    print(f'PREVIOUS STATE: {c.state}')
    c.trigger(event_type, event)
    print(f'NEW STATE: {c.state}')
