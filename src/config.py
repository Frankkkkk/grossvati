from azure.communication.callautomation import (
    PhoneNumberIdentifier,
)

TTS_LANG = "de-DE-ElkeNeural"

WEBSERVICE_URL = "https://grossvati.svc.ch/"
ACS_CONNECTION_STRING = "endpoint=https://grossvati.communication.azure.com/;accesskey=XXXXXXXX"
COG_SERV_ENDPOINT = "https://grossvati.cognitiveservices.azure.com/"


Frank_Number = PhoneNumberIdentifier("+41761111111")
Grossvati_Number = PhoneNumberIdentifier("+41781111111")
Azure_Number = PhoneNumberIdentifier("+41225159999")
