import enum

class ChatAvailabilityEnum(str, enum.Enum):
    OPEN_TO_CHAT = "open_to_chat"
    REQUEST_ONLY = "request_only"
    DO_NOT_DISTURB = "do_not_disturb"

class ChatRoomTypeEnum(str, enum.Enum): # We might not use this if is_group is sufficient
    DIRECT = "direct"
    GROUP = "group"

class ChatRequestStatusEnum(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    CANCELLED = "cancelled" # If requester cancels

class VoteTypeEnum(str, enum.Enum):
    UPVOTE = "upvote"
    DOWNVOTE = "downvote"

class RelationshipTypeEnum(str, enum.Enum):
    MUTE = "mute"
    BLOCK = "block"

class ReportedItemTypeEnum(str, enum.Enum):
    USER = "user"
    POST = "post"
    COMMENT = "comment"

class ReportStatusEnum(str, enum.Enum):
    PENDING = "pending"
    REVIEWED_ACTION_TAKEN = "reviewed_action_taken"
    REVIEWED_NO_ACTION = "reviewed_no_action"
    DISMISSED = "dismissed"

class NotificationTypeEnum(str, enum.Enum):
    NEW_COMMENT_ON_POST = "new_comment_on_post"
    NEW_CHAT_MESSAGE = "new_chat_message"
    CHAT_REQUEST_RECEIVED = "chat_request_received"
    CHAT_REQUEST_ACCEPTED = "chat_request_accepted"
    CHAT_REQUEST_DECLINED = "chat_request_declined"
    # Add other types as needed

class NotificationStatusEnum(str, enum.Enum):
    UNREAD = "unread"
    READ = "read"
    ARCHIVED = "archived"
