from typing import Optional
from pydantic import Extra

from fidesops.schemas.base_class import BaseSchema


class PrivacyRequestIdentity(BaseSchema):
    """Some PII grouping pertaining to a human"""

    phone_number: Optional[str] = None
    email: Optional[str] = None

    class Config:
        """Only allow phone_number and email to be supplied"""

        extra = Extra.forbid
