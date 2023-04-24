from typing import Any, Dict, Optional, Tuple
import uuid
from uuid import UUID
from session import Session
import datetime
import jwt
import hmac
import time
import atexit
import datetime
from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore


class Sessions:
    """Manages the REPL sessions."""

    def __init__(
        self,
        secret_key: bytes,
        check_time: datetime.timedelta,
        last_time_limit: datetime.timedelta,
        token_lifespan: datetime.timedelta,
        response_size_limit: Optional[int],
        compute_time_limit: datetime.timedelta,
        session_amount_limit: Optional[int],
    ) -> None:
        self.secret_key = secret_key.hex()
        self.algorithm = "HS256"
        self.sessions: Dict[str, Session] = dict()
        self.last_used: Dict[str, float] = dict()
        self.last_time_limit = last_time_limit
        self.token_lifespan = token_lifespan
        self.response_size_limit = response_size_limit
        self.compute_time_limit = compute_time_limit
        self.session_amount_limit = session_amount_limit

        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(
            func=self.cleanup, trigger="interval", seconds=check_time.seconds
        )
        self.scheduler.start()
        atexit.register(lambda: self.scheduler.shutdown())
        super().__init__()

    def cleanup(self):
        """
        Removes sessions if the token ran out or if the session was not
        interacted with within the time limit set by self.last_time_limit.
        """
        for token, last_used in list(self.last_used.items()):
            if time.time() - last_used > self.last_time_limit.seconds:
                self.remove(token)
            elif self.decode_token(token) is None:
                self.remove(token)

    def encode_id(self, identifier: str) -> str:
        """
        Given an id create a JSON Web Token and saves the time it was encoded.
        """
        payload = {
            "exp": datetime.datetime.utcnow() + self.token_lifespan,
            "iat": datetime.datetime.utcnow(),
            "sub": identifier,
        }

        encoding = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        self.last_used[encoding] = time.time()

        return encoding

    def decode_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Tries to decode the token, if possible the time it was decoded is saved
        and the id is returned. If it could not be decoded for some reason None
        is returned.
        """
        try:
            decoding = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            self.last_used[token] = time.time()
            return decoding
        except jwt.ExpiredSignatureError:
            pass
        except jwt.InvalidTokenError:
            pass

        return None

    def create_session(self) -> Optional[Tuple[str, Session]]:
        """
        Tries to create a session if the session limit is reached then None is
        returned. Otherwise the token and session object is returned.
        """
        if self.session_amount_limit is not None and self.session_amount_limit <= len(
            self.sessions
        ):
            return None

        identifier = uuid.uuid4().hex  # Is guarenteed to be unique.
        token = self.encode_id(identifier)  # JWTs are unique since the ids are unique.
        session = Session(
            identifier=identifier,
            compute_time_limit=self.compute_time_limit,
            response_size_limit=self.response_size_limit,
        )
        self.sessions[token] = session
        return token, session

    def verify(self, token: str) -> bool:
        """
        Returns true if the token is valid and false if the token is not valid.
        """
        decoding = self.decode_token(token)
        if decoding is None:
            return False

        identifier = decoding["sub"]
        session = self.get(token)

        if session is None:
            return False

        # Prevents time analysis
        return hmac.compare_digest(identifier, session.identifier)

    def get(self, token: str) -> Optional[Session]:
        """Gets the session that belongs to that token."""
        return self.sessions.get(token)

    def remove(self, token: str):
        """Removes session that belongs to the token and ends the session."""
        session = self.sessions.pop(token, None)

        if session is not None:
            session.kill()

        self.last_used.pop(token, None)
