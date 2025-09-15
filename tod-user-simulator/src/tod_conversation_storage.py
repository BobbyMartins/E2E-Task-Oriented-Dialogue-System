import json
import os
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging
from dataclasses import dataclass, asdict
from conversation_storage import ConversationStorage

logger = logging.getLogger(__name__)

@dataclass
class FeedbackData:
    """Data class for structured feedback collection."""
    # Task-level metrics
    task_success_rate: int  # 1-5 scale
    user_satisfaction: int  # 1-5 scale
    
    # Turn-level metrics  
    appropriateness: int  # 1-5 scale
    naturalness: int  # 1-5 scale
    coherence: int  # 1-5 scale
    
    # Dialogue-level metrics
    efficiency: int  # 1-5 scale
    conciseness: int  # 1-5 scale
    
    # Optional text feedback
    comments: Optional[str] = None
    
    # Metadata
    feedback_timestamp: Optional[datetime] = None
    session_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        if self.feedback_timestamp:
            data['feedback_timestamp'] = self.feedback_timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'FeedbackData':
        """Create from dictionary."""
        if 'feedback_timestamp' in data and data['feedback_timestamp']:
            data['feedback_timestamp'] = datetime.fromisoformat(data['feedback_timestamp'])
        return cls(**data)

@dataclass
class ConversationTurn:
    """Data class for individual conversation turns."""
    turn_number: int
    sender: str  # 'user' or 'bot'
    content: str
    timestamp: datetime
    model_metadata: Optional[Dict] = None
    processing_time: Optional[float] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ConversationTurn':
        """Create from dictionary."""
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)

@dataclass
class TODSession:
    """Data class for TOD session information."""
    session_id: str
    domain: str
    model_type: str  # 'bedrock' or 'grpotod'
    assignment_method: str  # 'random' or 'manual'
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = 'active'  # 'active', 'completed', 'abandoned'
    turns: List[ConversationTurn] = None
    domain_config: Optional[Dict] = None
    
    def __post_init__(self):
        if self.turns is None:
            self.turns = []
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['start_time'] = self.start_time.isoformat()
        if self.end_time:
            data['end_time'] = self.end_time.isoformat()
        data['turns'] = [turn.to_dict() for turn in self.turns]
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TODSession':
        """Create from dictionary."""
        data['start_time'] = datetime.fromisoformat(data['start_time'])
        if data.get('end_time'):
            data['end_time'] = datetime.fromisoformat(data['end_time'])
        if 'turns' in data:
            data['turns'] = [ConversationTurn.from_dict(turn) for turn in data['turns']]
        return cls(**data)


class TODConversationStorage(ConversationStorage):
    """Extended conversation storage for Task-Oriented Dialogue data."""
    
    def __init__(self, storage_dir='conversation_history'):
        """Initialize the TOD conversation storage.
        
        Args:
            storage_dir (str): Directory to store conversation history files.
        """
        super().__init__(storage_dir)
        
        # Path to TOD-specific index file
        self.tod_index_path = os.path.join(storage_dir, 'tod_index.json')
        
        # Initialize or load the TOD index
        if os.path.exists(self.tod_index_path):
            try:
                with open(self.tod_index_path, 'r') as f:
                    self.tod_index = json.load(f)
            except json.JSONDecodeError:
                logger.error(f"Error loading TOD index from {self.tod_index_path}")
                self.tod_index = {'conversations': []}
        else:
            self.tod_index = {'conversations': []}
    
    def save_tod_conversation(self, session: TODSession, feedback: Optional[FeedbackData] = None) -> str:
        """Save a TOD conversation to storage.
        
        Args:
            session (TODSession): The TOD session data.
            feedback (FeedbackData, optional): Feedback data for the conversation.
            
        Returns:
            str: The ID of the saved conversation.
        """
        # Generate a unique ID for the conversation
        conversation_id = str(uuid.uuid4())
        
        # Add timestamp
        timestamp = time.time()
        date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        
        # Calculate metadata
        total_turns = len(session.turns)
        response_times = [turn.processing_time for turn in session.turns 
                         if turn.processing_time is not None and turn.sender == 'bot']
        average_response_time = sum(response_times) / len(response_times) if response_times else None
        
        # Create the conversation record for TOD index
        tod_conversation_record = {
            'id': conversation_id,
            'session_id': session.session_id,
            'timestamp': timestamp,
            'date': date_str,
            'domain': session.domain,
            'model_type': session.model_type,
            'assignment_method': session.assignment_method,
            'status': session.status,
            'total_turns': total_turns,
            'start_time': session.start_time.isoformat(),
            'end_time': session.end_time.isoformat() if session.end_time else None,
            'has_feedback': feedback is not None,
            'average_response_time': average_response_time
        }
        
        # Add to TOD index
        self.tod_index['conversations'].append(tod_conversation_record)
        
        # Save the TOD index
        with open(self.tod_index_path, 'w') as f:
            json.dump(self.tod_index, f, indent=2)
        
        # Create the full conversation data structure
        conversation_data = {
            'conversation_id': conversation_id,
            'session_id': session.session_id,
            'domain': session.domain,
            'model_type': session.model_type,
            'assignment_method': session.assignment_method,
            'start_time': session.start_time.isoformat(),
            'end_time': session.end_time.isoformat() if session.end_time else None,
            'conversation': {
                'messages': [turn.to_dict() for turn in session.turns]
            },
            'domain_config': session.domain_config,
            'feedback': feedback.to_dict() if feedback else None,
            'metadata': {
                'total_turns': total_turns,
                'completion_status': session.status,
                'model_response_times': response_times,
                'average_response_time': average_response_time
            }
        }
        
        # Save the full conversation data to a separate file
        conversation_path = os.path.join(self.storage_dir, f"tod_{conversation_id}.json")
        with open(conversation_path, 'w') as f:
            json.dump(conversation_data, f, indent=2)
        
        # Also add to the main index for compatibility
        main_conversation_record = {
            'id': conversation_id,
            'timestamp': timestamp,
            'date': date_str,
            'metadata': {
                'type': 'tod',
                'domain': session.domain,
                'model_type': session.model_type,
                'session_id': session.session_id
            },
            'summary': self._generate_tod_summary(session)
        }
        
        self.index['conversations'].append(main_conversation_record)
        
        # Save the main index
        with open(self.index_path, 'w') as f:
            json.dump(self.index, f, indent=2)
        
        return conversation_id
    
    def get_conversations_by_model(self, model_type: str) -> List[Dict]:
        """Get conversations filtered by model type.
        
        Args:
            model_type (str): The model type to filter by ('bedrock' or 'grpotod').
            
        Returns:
            List[Dict]: List of conversation records matching the model type.
        """
        return [conv for conv in self.tod_index['conversations'] 
                if conv['model_type'] == model_type]
    
    def get_conversations_by_domain(self, domain: str) -> List[Dict]:
        """Get conversations filtered by domain.
        
        Args:
            domain (str): The domain to filter by ('hotel', 'restaurant', 'flight').
            
        Returns:
            List[Dict]: List of conversation records matching the domain.
        """
        return [conv for conv in self.tod_index['conversations'] 
                if conv['domain'] == domain]
    
    def get_conversations_by_filters(self, filters: Dict[str, Any]) -> List[Dict]:
        """Get conversations filtered by multiple criteria.
        
        Args:
            filters (Dict[str, Any]): Dictionary of filters to apply.
                Supported keys: model_type, domain, status, has_feedback, date_from, date_to
            
        Returns:
            List[Dict]: List of conversation records matching the filters.
        """
        conversations = self.tod_index['conversations']
        
        for key, value in filters.items():
            if key == 'model_type':
                conversations = [c for c in conversations if c['model_type'] == value]
            elif key == 'domain':
                conversations = [c for c in conversations if c['domain'] == value]
            elif key == 'status':
                conversations = [c for c in conversations if c['status'] == value]
            elif key == 'has_feedback':
                conversations = [c for c in conversations if c['has_feedback'] == value]
            elif key == 'date_from':
                conversations = [c for c in conversations if c['timestamp'] >= value]
            elif key == 'date_to':
                conversations = [c for c in conversations if c['timestamp'] <= value]
        
        return conversations
    
    def get_feedback_summary(self, filters: Optional[Dict] = None) -> Dict:
        """Get summary statistics of feedback data.
        
        Args:
            filters (Dict, optional): Filters to apply before calculating summary.
            
        Returns:
            Dict: Summary statistics of feedback data.
        """
        conversations = self.tod_index['conversations']
        
        # Apply filters if provided
        if filters:
            conversations = self.get_conversations_by_filters(filters)
        
        # Get conversations with feedback
        conversations_with_feedback = [c for c in conversations if c['has_feedback']]
        
        if not conversations_with_feedback:
            return {
                'total_conversations': len(conversations),
                'conversations_with_feedback': 0,
                'feedback_rate': 0.0,
                'average_scores': {}
            }
        
        # Load feedback data for detailed analysis
        feedback_scores = {
            'task_success_rate': [],
            'user_satisfaction': [],
            'appropriateness': [],
            'naturalness': [],
            'coherence': [],
            'efficiency': [],
            'conciseness': []
        }
        
        for conv in conversations_with_feedback:
            conversation_data = self.get_tod_conversation(conv['id'])
            if conversation_data and conversation_data.get('feedback'):
                feedback = conversation_data['feedback']
                for metric in feedback_scores.keys():
                    if metric in feedback:
                        feedback_scores[metric].append(feedback[metric])
        
        # Calculate averages
        average_scores = {}
        for metric, scores in feedback_scores.items():
            if scores:
                average_scores[metric] = sum(scores) / len(scores)
        
        return {
            'total_conversations': len(conversations),
            'conversations_with_feedback': len(conversations_with_feedback),
            'feedback_rate': len(conversations_with_feedback) / len(conversations) if conversations else 0.0,
            'average_scores': average_scores,
            'score_distributions': {metric: self._calculate_distribution(scores) 
                                  for metric, scores in feedback_scores.items() if scores}
        }
    
    def get_tod_conversation(self, conversation_id: str) -> Optional[Dict]:
        """Get a specific TOD conversation by ID.
        
        Args:
            conversation_id (str): The ID of the conversation to retrieve.
            
        Returns:
            Dict: The conversation data, or None if not found.
        """
        conversation_path = os.path.join(self.storage_dir, f"tod_{conversation_id}.json")
        
        if not os.path.exists(conversation_path):
            return None
        
        try:
            with open(conversation_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Error loading TOD conversation from {conversation_path}")
            return None
    
    def export_data(self, format: str = 'json', filters: Optional[Dict] = None) -> str:
        """Export conversation data for analysis.
        
        Args:
            format (str): Export format ('json' or 'csv').
            filters (Dict, optional): Filters to apply before export.
            
        Returns:
            str: Path to the exported file.
        """
        conversations = self.tod_index['conversations']
        
        # Apply filters if provided
        if filters:
            conversations = self.get_conversations_by_filters(filters)
        
        # Generate export filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if format.lower() == 'json':
            export_path = os.path.join(self.storage_dir, f'tod_export_{timestamp}.json')
            
            # Load full conversation data for export
            export_data = []
            for conv_summary in conversations:
                full_conv = self.get_tod_conversation(conv_summary['id'])
                if full_conv:
                    export_data.append(full_conv)
            
            with open(export_path, 'w') as f:
                json.dump(export_data, f, indent=2)
        
        elif format.lower() == 'csv':
            import csv
            export_path = os.path.join(self.storage_dir, f'tod_export_{timestamp}.csv')
            
            with open(export_path, 'w', newline='') as csvfile:
                fieldnames = [
                    'conversation_id', 'session_id', 'domain', 'model_type', 
                    'assignment_method', 'start_time', 'end_time', 'total_turns',
                    'completion_status', 'average_response_time', 'has_feedback'
                ]
                
                # Add feedback fields if any conversations have feedback
                if any(conv['has_feedback'] for conv in conversations):
                    fieldnames.extend([
                        'task_success_rate', 'user_satisfaction', 'appropriateness',
                        'naturalness', 'coherence', 'efficiency', 'conciseness', 'comments'
                    ])
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for conv_summary in conversations:
                    full_conv = self.get_tod_conversation(conv_summary['id'])
                    if full_conv:
                        row = {
                            'conversation_id': full_conv['conversation_id'],
                            'session_id': full_conv['session_id'],
                            'domain': full_conv['domain'],
                            'model_type': full_conv['model_type'],
                            'assignment_method': full_conv['assignment_method'],
                            'start_time': full_conv['start_time'],
                            'end_time': full_conv['end_time'],
                            'total_turns': full_conv['metadata']['total_turns'],
                            'completion_status': full_conv['metadata']['completion_status'],
                            'average_response_time': full_conv['metadata']['average_response_time'],
                            'has_feedback': full_conv['feedback'] is not None
                        }
                        
                        # Add feedback data if available
                        if full_conv['feedback']:
                            feedback = full_conv['feedback']
                            row.update({
                                'task_success_rate': feedback.get('task_success_rate'),
                                'user_satisfaction': feedback.get('user_satisfaction'),
                                'appropriateness': feedback.get('appropriateness'),
                                'naturalness': feedback.get('naturalness'),
                                'coherence': feedback.get('coherence'),
                                'efficiency': feedback.get('efficiency'),
                                'conciseness': feedback.get('conciseness'),
                                'comments': feedback.get('comments', '')
                            })
                        
                        writer.writerow(row)
        
        else:
            raise ValueError(f"Unsupported export format: {format}")
        
        return export_path
    
    def _generate_tod_summary(self, session: TODSession) -> Dict:
        """Generate a summary of the TOD conversation.
        
        Args:
            session (TODSession): The TOD session data.
            
        Returns:
            Dict: A summary of the conversation.
        """
        turns = session.turns
        turn_count = len(turns)
        
        # Get first and last messages for preview
        first_message = turns[0].content if turn_count > 0 else ""
        last_message = turns[-1].content if turn_count > 0 else ""
        
        # Truncate messages for preview
        max_preview_length = 50
        if len(first_message) > max_preview_length:
            first_message = first_message[:max_preview_length] + "..."
        if len(last_message) > max_preview_length:
            last_message = last_message[:max_preview_length] + "..."
        
        return {
            'turn_count': turn_count,
            'first_message': first_message,
            'last_message': last_message,
            'domain': session.domain,
            'model_type': session.model_type,
            'status': session.status
        }
    
    def _calculate_distribution(self, scores: List[int]) -> Dict[int, int]:
        """Calculate score distribution.
        
        Args:
            scores (List[int]): List of scores.
            
        Returns:
            Dict[int, int]: Distribution of scores.
        """
        distribution = {}
        for score in scores:
            distribution[score] = distribution.get(score, 0) + 1
        return distribution
    
    def get_model_comparison_stats(self) -> Dict:
        """Get comparative statistics between models.
        
        Returns:
            Dict: Comparison statistics between Bedrock and GRPOTOD models.
        """
        bedrock_conversations = self.get_conversations_by_model('bedrock')
        grpotod_conversations = self.get_conversations_by_model('grpotod')
        
        bedrock_feedback = self.get_feedback_summary({'model_type': 'bedrock'})
        grpotod_feedback = self.get_feedback_summary({'model_type': 'grpotod'})
        
        # Calculate response time statistics
        bedrock_response_times = []
        grpotod_response_times = []
        
        for conv in bedrock_conversations:
            full_conv = self.get_tod_conversation(conv['id'])
            if full_conv and full_conv['metadata']['average_response_time']:
                bedrock_response_times.append(full_conv['metadata']['average_response_time'])
        
        for conv in grpotod_conversations:
            full_conv = self.get_tod_conversation(conv['id'])
            if full_conv and full_conv['metadata']['average_response_time']:
                grpotod_response_times.append(full_conv['metadata']['average_response_time'])
        
        return {
            'bedrock': {
                'total_conversations': len(bedrock_conversations),
                'feedback_summary': bedrock_feedback,
                'average_response_time': sum(bedrock_response_times) / len(bedrock_response_times) if bedrock_response_times else None,
                'completion_rate': len([c for c in bedrock_conversations if c['status'] == 'completed']) / len(bedrock_conversations) if bedrock_conversations else 0
            },
            'grpotod': {
                'total_conversations': len(grpotod_conversations),
                'feedback_summary': grpotod_feedback,
                'average_response_time': sum(grpotod_response_times) / len(grpotod_response_times) if grpotod_response_times else None,
                'completion_rate': len([c for c in grpotod_conversations if c['status'] == 'completed']) / len(grpotod_conversations) if grpotod_conversations else 0
            }
        }