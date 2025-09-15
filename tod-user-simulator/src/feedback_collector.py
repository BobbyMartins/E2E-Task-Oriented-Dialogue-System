"""
Feedback Collection System for TOD User Simulator

This module provides functionality to collect, validate, and analyze feedback
from users after completing task-oriented dialogue conversations.
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class FeedbackData:
    """
    Structured feedback data for TOD conversations.
    
    Includes task-level, turn-level, and dialogue-level metrics
    as specified in requirements 4.2, 4.3, 4.4.
    """
    # Task-level metrics (Requirement 4.2)
    task_success_rate: int  # 1-5 scale
    user_satisfaction: int  # 1-5 scale
    
    # Turn-level metrics (Requirement 4.3)
    appropriateness: int  # 1-5 scale
    naturalness: int  # 1-5 scale
    coherence: int  # 1-5 scale
    
    # Dialogue-level metrics (Requirement 4.4)
    efficiency: int  # 1-5 scale
    conciseness: int  # 1-5 scale
    
    # Optional text feedback
    comments: Optional[str] = None
    
    # Metadata
    feedback_timestamp: Optional[datetime] = None
    session_id: Optional[str] = None
    
    def __post_init__(self):
        """Set timestamp if not provided."""
        if self.feedback_timestamp is None:
            self.feedback_timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert feedback data to dictionary format."""
        data = asdict(self)
        # Convert datetime to ISO string for JSON serialization
        if self.feedback_timestamp:
            data['feedback_timestamp'] = self.feedback_timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FeedbackData':
        """Create FeedbackData from dictionary."""
        # Convert ISO string back to datetime
        if 'feedback_timestamp' in data and isinstance(data['feedback_timestamp'], str):
            data['feedback_timestamp'] = datetime.fromisoformat(data['feedback_timestamp'])
        return cls(**data)


class FeedbackValidator:
    """Validates feedback data according to specified constraints."""
    
    RATING_FIELDS = [
        'task_success_rate', 'user_satisfaction', 'appropriateness',
        'naturalness', 'coherence', 'efficiency', 'conciseness'
    ]
    
    @staticmethod
    def validate_feedback(feedback_data: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate feedback data structure and values.
        
        Args:
            feedback_data: Dictionary containing feedback data
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        # Check required fields
        required_fields = FeedbackValidator.RATING_FIELDS
        for field in required_fields:
            if field not in feedback_data:
                errors.append(f"Missing required field: {field}")
            elif not isinstance(feedback_data[field], int):
                errors.append(f"Field {field} must be an integer")
            elif not (1 <= feedback_data[field] <= 5):
                errors.append(f"Field {field} must be between 1 and 5")
        
        # Validate optional fields
        if 'comments' in feedback_data and feedback_data['comments'] is not None:
            if not isinstance(feedback_data['comments'], str):
                errors.append("Comments field must be a string")
            elif len(feedback_data['comments']) > 1000:
                errors.append("Comments field must be less than 1000 characters")
        
        if 'session_id' in feedback_data and feedback_data['session_id'] is not None:
            if not isinstance(feedback_data['session_id'], str):
                errors.append("Session ID must be a string")
        
        return len(errors) == 0, errors


class FeedbackCollector:
    """
    Main feedback collection system for TOD conversations.
    
    Handles feedback collection, validation, storage, and analysis
    as specified in requirements 4.1-4.6.
    """
    
    def __init__(self, storage_path: str = "feedback_data"):
        """
        Initialize feedback collector.
        
        Args:
            storage_path: Directory path for storing feedback data
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        self.validator = FeedbackValidator()
        
        # Initialize feedback storage file
        self.feedback_file = self.storage_path / "feedback.json"
        if not self.feedback_file.exists():
            self._initialize_storage()
    
    def _initialize_storage(self):
        """Initialize the feedback storage file."""
        initial_data = {
            "feedback_entries": [],
            "metadata": {
                "created": datetime.now().isoformat(),
                "version": "1.0"
            }
        }
        with open(self.feedback_file, 'w') as f:
            json.dump(initial_data, f, indent=2)
    
    def get_feedback_form_template(self) -> Dict[str, Any]:
        """
        Get the feedback form template structure.
        
        Returns:
            Dictionary containing form structure and field definitions
        """
        return {
            "form_sections": {
                "task_level": {
                    "title": "Task Completion",
                    "description": "Rate how well the system helped you complete your task",
                    "fields": {
                        "task_success_rate": {
                            "label": "Task Success Rate",
                            "description": "How successfully did the system help you complete your task?",
                            "type": "rating",
                            "scale": "1-5",
                            "labels": {
                                "1": "Not at all successful",
                                "2": "Slightly successful", 
                                "3": "Moderately successful",
                                "4": "Very successful",
                                "5": "Extremely successful"
                            }
                        },
                        "user_satisfaction": {
                            "label": "User Satisfaction",
                            "description": "How satisfied are you with the overall interaction?",
                            "type": "rating",
                            "scale": "1-5",
                            "labels": {
                                "1": "Very dissatisfied",
                                "2": "Dissatisfied",
                                "3": "Neutral",
                                "4": "Satisfied", 
                                "5": "Very satisfied"
                            }
                        }
                    }
                },
                "turn_level": {
                    "title": "Conversation Quality",
                    "description": "Rate the quality of individual responses",
                    "fields": {
                        "appropriateness": {
                            "label": "Appropriateness",
                            "description": "How appropriate were the system's responses?",
                            "type": "rating",
                            "scale": "1-5"
                        },
                        "naturalness": {
                            "label": "Naturalness", 
                            "description": "How natural did the conversation feel?",
                            "type": "rating",
                            "scale": "1-5"
                        },
                        "coherence": {
                            "label": "Coherence",
                            "description": "How coherent and logical were the responses?",
                            "type": "rating",
                            "scale": "1-5"
                        }
                    }
                },
                "dialogue_level": {
                    "title": "Overall Dialogue",
                    "description": "Rate the overall conversation flow",
                    "fields": {
                        "efficiency": {
                            "label": "Efficiency",
                            "description": "How efficiently did the system handle your request?",
                            "type": "rating",
                            "scale": "1-5"
                        },
                        "conciseness": {
                            "label": "Conciseness",
                            "description": "Were the responses appropriately concise?",
                            "type": "rating", 
                            "scale": "1-5"
                        }
                    }
                },
                "additional": {
                    "title": "Additional Feedback",
                    "fields": {
                        "comments": {
                            "label": "Additional Comments",
                            "description": "Any additional feedback or comments?",
                            "type": "textarea",
                            "optional": True,
                            "max_length": 1000
                        }
                    }
                }
            }
        }
    
    def collect_feedback(self, session_id: str, feedback_data: Dict[str, Any]) -> tuple[bool, str]:
        """
        Collect and store feedback for a conversation session.
        
        Args:
            session_id: Unique identifier for the conversation session
            feedback_data: Dictionary containing feedback ratings and comments
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Validate feedback data (Requirement 4.6)
            is_valid, errors = self.validator.validate_feedback(feedback_data)
            if not is_valid:
                error_msg = f"Validation failed: {'; '.join(errors)}"
                logger.error(f"Feedback validation failed for session {session_id}: {error_msg}")
                return False, error_msg
            
            # Create FeedbackData object
            feedback_data['session_id'] = session_id
            feedback_obj = FeedbackData.from_dict(feedback_data)
            
            # Store feedback (Requirement 4.5)
            success = self._store_feedback(feedback_obj)
            if success:
                logger.info(f"Feedback collected successfully for session {session_id}")
                return True, "Feedback collected successfully"
            else:
                return False, "Failed to store feedback"
                
        except Exception as e:
            error_msg = f"Error collecting feedback: {str(e)}"
            logger.error(f"Feedback collection error for session {session_id}: {error_msg}")
            return False, error_msg
    
    def _store_feedback(self, feedback: FeedbackData) -> bool:
        """
        Store feedback data to persistent storage.
        
        Args:
            feedback: FeedbackData object to store
            
        Returns:
            True if storage successful, False otherwise
        """
        try:
            # Load existing data
            with open(self.feedback_file, 'r') as f:
                data = json.load(f)
            
            # Add new feedback entry
            data['feedback_entries'].append(feedback.to_dict())
            data['metadata']['last_updated'] = datetime.now().isoformat()
            data['metadata']['total_entries'] = len(data['feedback_entries'])
            
            # Save updated data
            with open(self.feedback_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to store feedback: {str(e)}")
            return False
    
    def get_feedback_summary(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate summary statistics for collected feedback.
        
        Args:
            filters: Optional filters to apply (e.g., by session_id, date range)
            
        Returns:
            Dictionary containing summary statistics
        """
        try:
            # Load feedback data
            with open(self.feedback_file, 'r') as f:
                data = json.load(f)
            
            feedback_entries = data['feedback_entries']
            
            # Apply filters if provided
            if filters:
                feedback_entries = self._apply_filters(feedback_entries, filters)
            
            if not feedback_entries:
                return {"message": "No feedback data found", "total_entries": 0}
            
            # Calculate summary statistics
            summary = {
                "total_entries": len(feedback_entries),
                "date_range": {
                    "earliest": min(entry['feedback_timestamp'] for entry in feedback_entries),
                    "latest": max(entry['feedback_timestamp'] for entry in feedback_entries)
                },
                "metrics": {}
            }
            
            # Calculate averages for each rating field
            for field in FeedbackValidator.RATING_FIELDS:
                values = [entry[field] for entry in feedback_entries if field in entry]
                if values:
                    summary["metrics"][field] = {
                        "average": round(sum(values) / len(values), 2),
                        "min": min(values),
                        "max": max(values),
                        "count": len(values)
                    }
            
            # Count entries with comments
            comments_count = sum(1 for entry in feedback_entries 
                               if entry.get('comments') and entry['comments'].strip())
            summary["comments_provided"] = comments_count
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to generate feedback summary: {str(e)}")
            return {"error": f"Failed to generate summary: {str(e)}"}
    
    def _apply_filters(self, feedback_entries: List[Dict], filters: Dict[str, Any]) -> List[Dict]:
        """Apply filters to feedback entries."""
        filtered_entries = feedback_entries
        
        # Filter by session_id
        if 'session_id' in filters:
            filtered_entries = [entry for entry in filtered_entries 
                              if entry.get('session_id') == filters['session_id']]
        
        # Filter by date range
        if 'start_date' in filters:
            start_date = filters['start_date']
            if isinstance(start_date, str):
                start_date = datetime.fromisoformat(start_date)
            filtered_entries = [entry for entry in filtered_entries
                              if datetime.fromisoformat(entry['feedback_timestamp']) >= start_date]
        
        if 'end_date' in filters:
            end_date = filters['end_date']
            if isinstance(end_date, str):
                end_date = datetime.fromisoformat(end_date)
            filtered_entries = [entry for entry in filtered_entries
                              if datetime.fromisoformat(entry['feedback_timestamp']) <= end_date]
        
        return filtered_entries
    
    def get_all_feedback(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieve all feedback entries, optionally filtered by session ID.
        
        Args:
            session_id: Optional session ID to filter by
            
        Returns:
            List of feedback entries
        """
        try:
            with open(self.feedback_file, 'r') as f:
                data = json.load(f)
            
            feedback_entries = data['feedback_entries']
            
            if session_id:
                feedback_entries = [entry for entry in feedback_entries 
                                  if entry.get('session_id') == session_id]
            
            return feedback_entries
            
        except Exception as e:
            logger.error(f"Failed to retrieve feedback: {str(e)}")
            return []
    
    def export_feedback_data(self, format_type: str = 'json', 
                           filters: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Export feedback data in specified format.
        
        Args:
            format_type: Export format ('json' or 'csv')
            filters: Optional filters to apply
            
        Returns:
            Path to exported file or None if failed
        """
        try:
            # Get filtered feedback data
            with open(self.feedback_file, 'r') as f:
                data = json.load(f)
            
            feedback_entries = data['feedback_entries']
            if filters:
                feedback_entries = self._apply_filters(feedback_entries, filters)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if format_type.lower() == 'json':
                export_file = self.storage_path / f"feedback_export_{timestamp}.json"
                with open(export_file, 'w') as f:
                    json.dump({
                        "exported_at": datetime.now().isoformat(),
                        "total_entries": len(feedback_entries),
                        "feedback_data": feedback_entries
                    }, f, indent=2)
                
            elif format_type.lower() == 'csv':
                import csv
                export_file = self.storage_path / f"feedback_export_{timestamp}.csv"
                
                if feedback_entries:
                    fieldnames = list(feedback_entries[0].keys())
                    with open(export_file, 'w', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(feedback_entries)
                else:
                    # Create empty CSV with headers
                    fieldnames = FeedbackValidator.RATING_FIELDS + ['comments', 'feedback_timestamp', 'session_id']
                    with open(export_file, 'w', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
            
            else:
                raise ValueError(f"Unsupported export format: {format_type}")
            
            logger.info(f"Feedback data exported to {export_file}")
            return str(export_file)
            
        except Exception as e:
            logger.error(f"Failed to export feedback data: {str(e)}")
            return None