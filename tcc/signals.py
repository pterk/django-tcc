"""
Signals relating to comments.
"""
from django.dispatch import Signal

# Sent just before a comment is saved
comment_will_be_posted = Signal(providing_args=["comment"])

# Sent just after a comment was saved.
comment_was_posted = Signal(providing_args=["comment"])

# Sent after a comment was "flagged" in some way.
comment_was_flagged = Signal(providing_args=["comment"])
