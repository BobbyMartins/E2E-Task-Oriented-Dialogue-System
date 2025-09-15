"""
Session Management System for TOD User Simulator

This module provides session management functionality including:
- Session creation with random model assignment
- Session state tracking and conversation history management
- Session cleanup and expiration handling
"""

import uuid
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import json
import threading
import time


class SessionStatus(Enum):
    """Enumeration of possible session statuses"""
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    EXPIRED = "expired"


@dataclass
class ConversationTurn:
    """Represents a single turn in a conversation"""
    turn_number: int
    sender: str  # 'user' or 'bot'
    content: str
    timestamp: datetime
    model_metadata: Optional[Dict] = None
    processing_time: Optional[float] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ConversationTurn':
        """Create from dictionary"""
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


@dataclass
class Session:
    """Represents a conversation session"""
    session_id: str
    domain: str
    model_type: str  # 'bedrock' or 'grpotod'
    conversation_history: List[ConversationTurn]
    start_time: datetime
    end_time: Optional[datetime] = None
    status: SessionStatus = SessionStatus.ACTIVE
    assignment_method: str = "random"  # 'random' or 'manual'
    user_id: Optional[str] = None
    last_activity: Optional[datetime] = None
    
    def __post_init__(self):
        """Initialize last_activity if not set"""
        if self.last_activity is None:
            self.last_activity = self.start_time
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['start_time'] = self.start_time.isoformat()
        data['end_time'] = self.end_time.isoformat() if self.end_time else None
        data['last_activity'] = self.last_activity.isoformat() if self.last_activity else None
        data['status'] = self.status.value
        data['conversation_history'] = [turn.to_dict() for turn in self.conversation_history]
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Session':
        """Create from dictionary"""
        data['start_time'] = datetime.fromisoformat(data['start_time'])
        data['end_time'] = datetime.fromisoformat(data['end_time']) if data['end_time'] else None
        data['last_activity'] = datetime.fromisoformat(data['last_activity']) if data['last_activity'] else None
        data['status'] = SessionStatus(data['status'])
        data['conversation_history'] = [ConversationTurn.from_dict(turn) for turn in data['conversation_history']]
        return cls(**data)
    
    def add_turn(self, sender: str, content: str, model_metadata: Optional[Dict] = None, 
                 processing_time: Optional[float] = None) -> None:
        """Add a new conversation turn"""
        turn_number = len(self.conversation_history) + 1
        turn = ConversationTurn(
            turn_number=turn_number,
            sender=sender,
            content=content,
            timestamp=datetime.now(),
            model_metadata=model_metadata,
            processing_time=processing_time
        )
        self.conversation_history.append(turn)
        self.last_activity = datetime.now()
    
    def get_conversation_text(self) -> List[str]:
        """Get conversation as list of text messages"""
        return [f"{turn.sender}: {turn.content}" for turn in self.conversation_history]
    
    def is_expired(self, expiration_hours: int = 24) -> bool:
        """Check if session has expired based on last activity"""
        if not self.last_activity:
            return False
        expiration_time = self.last_activity + timedelta(hours=expiration_hours)
        return datetime.now() > expiration_time


class SessionManager:
    """Manages conversation sessions for the TOD User Simulator"""
    
    def __init__(self, session_expiration_hours: int = 24, cleanup_interval_minutes: int = 60):
        """
        Initialize the SessionManager
        
        Args:
            session_expiration_hours: Hours after which inactive sessions expire
            cleanup_interval_minutes: Minutes between automatic cleanup runs
        """
        self.sessions: Dict[str, Session] = {}
        self.session_expiration_hours = session_expiration_hours
        self.cleanup_interval_minutes = cleanup_interval_minutes
        self._lock = threading.Lock()
        self._cleanup_thread = None
        self._stop_cleanup = False
        
        # Available models for random assignment
        self.available_models = ["bedrock", "grpotod"]
        
        # Start automatic cleanup
        self._start_cleanup_thread()
    
    def create_session(self, domain: str, model_type: Optional[str] = None, 
                      user_id: Optional[str] = None) -> Session:
        """
        Create a new conversation session
        
        Args:
            domain: The conversation domain (hotel, restaurant, flight)
            model_type: Specific model to use, or None for random assignment
            user_id: Optional user identifier
            
        Returns:
            Created Session object
        """
        with self._lock:
            session_id = str(uuid.uuid4())
            
            # Assign model randomly if not specified
            if model_type is None:
                model_type = random.choice(self.available_models)
                assignment_method = "random"
            else:
                assignment_method = "manual"
            
            # Validate model type
            if model_type not in self.available_models:
                raise ValueError(f"Invalid model type: {model_type}. Available: {self.available_models}")
            
            # Create new session
            session = Session(
                session_id=session_id,
                domain=domain,
                model_type=model_type,
                conversation_history=[],
                start_time=datetime.now(),
                assignment_method=assignment_method,
                user_id=user_id
            )
            
            self.sessions[session_id] = session
            return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """
        Retrieve a session by ID
        
        Args:
            session_id: The session identifier
            
        Returns:
            Session object if found, None otherwise
        """
        with self._lock:
            return self.sessions.get(session_id)
    
    def update_session(self, session_id: str, message: str, response: str, 
                      model_metadata: Optional[Dict] = None, 
                      processing_time: Optional[float] = None) -> bool:
        """
        Update a session with a new conversation turn
        
        Args:
            session_id: The session identifier
            message: User message
            response: Bot response
            model_metadata: Optional metadata from the model
            processing_time: Time taken to generate response
            
        Returns:
            True if session was updated, False if session not found
        """
        with self._lock:
            session = self.sessions.get(session_id)
            if not session:
                return False
            
            # Add user message
            session.add_turn("user", message)
            
            # Add bot response
            session.add_turn("bot", response, model_metadata, processing_time)
            
            return True
    
    def end_session(self, session_id: str, status: SessionStatus = SessionStatus.COMPLETED) -> bool:
        """
        End a session and mark it as completed or abandoned
        
        Args:
            session_id: The session identifier
            status: Final status for the session
            
        Returns:
            True if session was ended, False if session not found
        """
        with self._lock:
            session = self.sessions.get(session_id)
            if not session:
                return False
            
            session.status = status
            session.end_time = datetime.now()
            return True
    
    def get_active_sessions(self) -> List[Session]:
        """Get all active sessions"""
        with self._lock:
            return [session for session in self.sessions.values() 
                   if session.status == SessionStatus.ACTIVE]
    
    def get_sessions_by_model(self, model_type: str) -> List[Session]:
        """Get all sessions for a specific model"""
        with self._lock:
            return [session for session in self.sessions.values() 
                   if session.model_type == model_type]
    
    def get_sessions_by_domain(self, domain: str) -> List[Session]:
        """Get all sessions for a specific domain"""
        with self._lock:
            return [session for session in self.sessions.values() 
                   if session.domain == domain]
    
    def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions
        
        Returns:
            Number of sessions cleaned up
        """
        with self._lock:
            expired_sessions = []
            
            for session_id, session in self.sessions.items():
                if session.status == SessionStatus.ACTIVE and session.is_expired(self.session_expiration_hours):
                    session.status = SessionStatus.EXPIRED
                    session.end_time = datetime.now()
                    expired_sessions.append(session_id)
            
            return len(expired_sessions)
    
    def get_session_statistics(self) -> Dict[str, Any]:
        """Get statistics about current sessions"""
        with self._lock:
            stats = {
                "total_sessions": len(self.sessions),
                "active_sessions": len([s for s in self.sessions.values() if s.status == SessionStatus.ACTIVE]),
                "completed_sessions": len([s for s in self.sessions.values() if s.status == SessionStatus.COMPLETED]),
                "abandoned_sessions": len([s for s in self.sessions.values() if s.status == SessionStatus.ABANDONED]),
                "expired_sessions": len([s for s in self.sessions.values() if s.status == SessionStatus.EXPIRED]),
                "sessions_by_model": {},
                "sessions_by_domain": {},
                "average_conversation_length": 0
            }
            
            # Count by model
            for model in self.available_models:
                stats["sessions_by_model"][model] = len(self.get_sessions_by_model(model))
            
            # Count by domain (assuming common domains)
            domains = set(session.domain for session in self.sessions.values())
            for domain in domains:
                stats["sessions_by_domain"][domain] = len(self.get_sessions_by_domain(domain))
            
            # Calculate average conversation length
            if self.sessions:
                total_turns = sum(len(session.conversation_history) for session in self.sessions.values())
                stats["average_conversation_length"] = total_turns / len(self.sessions)
            
            return stats
    
    def _start_cleanup_thread(self) -> None:
        """Start the automatic cleanup thread"""
        def cleanup_worker():
            while not self._stop_cleanup:
                try:
                    self.cleanup_expired_sessions()
                    time.sleep(self.cleanup_interval_minutes * 60)
                except Exception as e:
                    print(f"Error in session cleanup: {e}")
                    time.sleep(60)  # Wait a minute before retrying
        
        self._cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        self._cleanup_thread.start()
    
    def stop_cleanup(self) -> None:
        """Stop the automatic cleanup thread"""
        self._stop_cleanup = True
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)
    
    def save_sessions_to_file(self, filepath: str) -> None:
        """Save all sessions to a JSON file"""
        with self._lock:
            sessions_data = {
                session_id: session.to_dict() 
                for session_id, session in self.sessions.items()
            }
            
            with open(filepath, 'w') as f:
                json.dump(sessions_data, f, indent=2)
    
    def load_sessions_from_file(self, filepath: str) -> None:
        """Load sessions from a JSON file"""
        try:
            with open(filepath, 'r') as f:
                sessions_data = json.load(f)
            
            with self._lock:
                self.sessions = {
                    session_id: Session.from_dict(session_data)
                    for session_id, session_data in sessions_data.items()
                }
        except FileNotFoundError:
            print(f"Session file {filepath} not found, starting with empty sessions")
        except Exception as e:
            print(f"Error loading sessions from {filepath}: {e}")
    
    def __del__(self):
        """Cleanup when the SessionManager is destroyed"""
        self.stop_cleanup()