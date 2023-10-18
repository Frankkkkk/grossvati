import logging

from transitions import Machine

from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.communication.callautomation import (
    CallAutomationClient,
    CallConnectionClient,
    PhoneNumberIdentifier,
    CallRejectReason,
    RecognitionChoice,
)
from azure.communication.callautomation import FileSource, TextSource

import enums
import logic
import config
import contacts


def sanitize_speech_return(s: str) -> str:
    logging.info(f'RECOG: Received {s}')
    return s.lower().replace('.', '').strip()

class Call(object):

    # Define some states. Most of the time, narcoleptic superheroes are just like
    # everyone else. Except for...
    states = [
        'waiting_newcall',
        'ask_name_speech', 'ask_name_choice',
        'recognized_failed',
        'choose_contact', 'choose_multiple_contacts', 'choose_multiple_contacts_reply', 'choose_multiple_no_more_contacts',
        'call_participant', 'calling', 'long_term_call',
        'hangup']

    def __init__(self, call_connection_id, initial_caller):

        self.call_connection = CallConnectionClient.from_connection_string(config.ACS_CONNECTION_STRING, call_connection_id)
        self.initial_caller = initial_caller

        self.contacts_list = []


        # Initialize the state machine
        self.machine = Machine(model=self, states=Call.states, initial='waiting_newcall')

        self.machine.add_transition(trigger=enums.CALL_CONNECTED_EVENT, source='waiting_newcall', dest='ask_name_speech')

        self.machine.add_transition(enums.RECOGNIZE_COMPLETED_EVENT, 'ask_name_speech', 'choose_contact')
        self.machine.add_transition(enums.RECOGNIZE_COMPLETED_EVENT, 'ask_name_choice', 'choose_contact')
        self.machine.add_transition(enums.RECOGNIZE_COMPLETED_EVENT, 'recognized_failed', 'choose_contact')

        self.machine.add_transition(enums.INTERNAL_KNOWN_CONTACT, 'choose_contact', 'call_participant')
        self.machine.add_transition(enums.INTERNAL_UNKNOWN_CONTACT, 'choose_contact', 'recognized_failed')

        self.machine.add_transition(enums.INTERNAL_MULTIPLE_CONTACTS, 'choose_contact', 'choose_multiple_contacts')
        self.machine.add_transition(enums.RECOGNIZE_COMPLETED_EVENT, 'choose_multiple_contacts', 'choose_multiple_contacts_reply')
        self.machine.add_transition(enums.RECOGNIZE_FAILED_EVENT, 'choose_multiple_contacts', 'choose_multiple_contacts')
        self.machine.add_transition(enums.INTERNAL_NO_MORE_CONTACTS, 'choose_multiple_contacts', 'choose_multiple_no_more_contacts')

        self.machine.add_transition(enums.INTERNAL_KNOWN_CONTACT, 'choose_multiple_contacts_reply', 'call_participant')
        self.machine.add_transition(enums.INTERNAL_MULTIPLE_CONTACTS, 'choose_multiple_contacts_reply', 'choose_multiple_contacts')

        self.machine.add_transition(enums.CONTINUE, 'choose_multiple_no_more_contacts', 'ask_name_speech')

        self.machine.add_transition(enums.RECOGNIZE_FAILED_EVENT, 'ask_name_speech', 'recognized_failed')
        self.machine.add_transition(enums.RECOGNIZE_FAILED_EVENT, 'ask_name_choice', 'recognized_failed')
        self.machine.add_transition(enums.RECOGNIZE_FAILED_EVENT, 'recognized_failed', 'recognized_failed')

        self.machine.add_transition(enums.PARTICIPANTS_UPDATED_EVENT, '*', None) # NOOP
        self.machine.add_transition(enums.ADD_PARTICIPANT_SUCCEEDED_EVENT, '*', None) # NOOP
        self.machine.add_transition(enums.PLAY_COMPLETED_EVENT, '*', None) # NOOP
        self.machine.add_transition(enums.PLAY_FAILED_EVENT, '*', 'hangup', before='play_failed') # NOOP

        self.machine.add_transition(enums.INTERNAL_CALLING, 'call_participant', 'calling')

        self.machine.add_transition(enums.PLAY_COMPLETED_EVENT, 'calling', 'hangup')
        self.machine.add_transition(enums.PARTICIPANTS_UPDATED_EVENT, 'calling', 'long_term_call')

        self.machine.add_transition(enums.CALL_DISCONNECTED_EVENT, '*', 'hangup')

        self.machine.on_enter_ask_name_speech('ask_name_speech')
        self.machine.on_enter_choose_contact('choose_contact_from_speech')
        self.machine.on_enter_choose_multiple_contacts('choose_multiple_contacts')
        self.machine.on_enter_choose_multiple_no_more_contacts('choose_multiple_no_more_contacts')
        self.machine.on_enter_choose_multiple_contacts_reply('choose_multiple_contacts_reply')
        self.machine.on_enter_recognized_failed('recognized_failed')
        self.machine.on_enter_call_participant('call_participant')
        self.machine.on_enter_long_term_call('long_term_call')

        self.machine.on_enter_hangup('hangup')


    def ask_name_speech(self, event=None):
        hello = TextSource("Wen möchten sie anrufen ?", voice_name=config.TTS_LANG)
        logging.debug(f'Will play >>{hello}')
        self.call_connection.play_media_to_all(hello, operation_context="HELLO")

        self.call_connection.start_recognizing_media(
            input_type="speech",
            target_participant=self.initial_caller,
            speech_language="de-CH",
            end_silence_timeout=2)
    
    def choose_contact_from_speech(self, event=None):
        speech_str = sanitize_speech_return(event.data['speechResult']['speech'])
        print(f"SPEECH WAS : {speech_str}")

        cts = contacts.get_matching_contacts(speech_str)
        self.contacts_list = cts # Used by KNOWN_CONTACT & MULTIPLE_CONTACTS
        if len(cts) == 0:
            self.trigger(enums.INTERNAL_UNKNOWN_CONTACT)
        elif len(cts) == 1:
            self.trigger(enums.INTERNAL_KNOWN_CONTACT, contact=cts[0])
        else:
            self.trigger(enums.INTERNAL_MULTIPLE_CONTACTS, cts)
            
    def choose_multiple_contacts(self, event=None):
        if len(self.contacts_list) == 0:
            # We no longer have contacts matching the input speech.
            self.trigger(enums.INTERNAL_NO_MORE_CONTACTS)
            return

        next_contact = self.contacts_list[0]
        will_call = TextSource(f"Mochten sie {next_contact.name} anrufen ?", voice_name=config.TTS_LANG)
        logging.debug(f'Will play >>{will_call}')
        self.call_connection.play_media_to_all(will_call, operation_context="HELLO")

        self.call_connection.start_recognizing_media(
            input_type="speech",
            target_participant=self.initial_caller,
            speech_language="de-CH",
            end_silence_timeout=2)

    def choose_multiple_contacts_reply(self, event=None):
        speech_str = sanitize_speech_return(event.data['speechResult']['speech'])
        print(f"SPEECH WAS : {speech_str}")

        if speech_str in ['ja', 'genau', 'gerne', ]:
            self.trigger(enums.INTERNAL_KNOWN_CONTACT, contact=self.contacts_list[0])
        else:
            self.contacts_list.pop(0)
            self.trigger(enums.INTERNAL_MULTIPLE_CONTACTS)


    def choose_multiple_no_more_contacts(self, event=None):
        will_call = TextSource(f"Ich habe keine Kontakte mehr", voice_name=config.TTS_LANG)
        logging.debug(f'Will play >>{will_call}')
        self.call_connection.play_media_to_all(will_call, operation_context="HELLO")

        self.trigger(enums.CONTINUE)


    def call_participant(self, contact: contacts.Contact, **kwargs):
        print(f'WILL CALL {contact}')

        # XXX FIXME
        self.call_connection.add_participant(PhoneNumberIdentifier(contact.number), source_caller_id_number=config.Azure_Number, invitation_timeout=30)

        will_call = TextSource(f"Ich werde {contact.name} anrufen. Einen Moment bitte", voice_name=config.TTS_LANG)
        logging.debug(f'Will play >>{will_call}')
        self.call_connection.play_media_to_all(will_call, operation_context="HELLO")
        # XXX if particiant gets the call

        calling_tone = FileSource(config.WEBSERVICE_URL + "res/ring_tone.wav")
        self.call_connection.play_media_to_all(calling_tone, operation_context="HELLO")
        #self.call_connection.play_media(calling_tone, play_to=self.initial_caller)

        #self.trigger(enums.INTERNAL_LONG_TERM_CALL)

    def recognized_failed(self, event=None):
        repeat = TextSource("Konnen sie das bitte wiederholen ?", voice_name=config.TTS_LANG)
        logging.debug(f'Will play >>{repeat}')
        self.call_connection.play_media_to_all(repeat, operation_context="HELLO")

        self.call_connection.start_recognizing_media(
            input_type="speech",
            target_participant=self.initial_caller,
            speech_language="de-CH",
            end_silence_timeout=2)



    def long_term_call(self):
        """ the wanted participant answered the phone. Stop the ring tone"""
        # The lazy way to cancel the ring tone
        self.call_connection.cancel_all_media_operations()

    def play_failed(self, event=None, **kwargs):
        logging.error(f'Couldnt play media: {event} {kwargs}')

    def hangup(self, event=None):
        try:
            self.call_connection.hang_up(is_for_everyone=True)
        except ResourceNotFoundError:
            # We hung up twice
            pass