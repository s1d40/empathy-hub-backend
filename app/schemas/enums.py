import enum 

class ChatAvailabilityEnum(str, enum.Enum):
    OPEN_TO_CHAT = "open_to_chat"
    REQUEST_ONLY = "request_only"
    DO_NOT_DISTURB = "do_not_disturb"
    