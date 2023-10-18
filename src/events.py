import logging
import pprint

from azure.eventgrid import SystemEventNames
from flask import current_app as app, Response, json
#from service.appointment_booking_service import AppointmentBookingService
#from service.call_automation_service import CallAutomationService

import logic


class EventsHandler:
    def handle_incoming_events(self, event):
        print(f'NEW EVENT: {event.event_type}')
        # this section is for handling initial handshaking with Event webhook registration
        if event.event_type == SystemEventNames.EventGridSubscriptionValidationEventName:
            validation_code = event.data['validationCode']
            validation_response = {'validationResponse': validation_code}
            return validation_response

        # Answer Incoming call with incoming call event data, incomingCallContext can be used to answer the call
        elif event.event_type == SystemEventNames.AcsIncomingCallEventName:
            logging.debug(f'Incoming call from {event}')
            logic.incoming_call(event)

    def handle_callback_events(self, event, initial_caller=None):
        call_connection_id = event.data['callConnectionId']
        app.logger.info("Callback received: %s, for call connection id:%s", event.type, call_connection_id)

        logic.handle_event(event, call_connection_id, initial_caller)

