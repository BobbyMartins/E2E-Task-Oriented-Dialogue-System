import json
import os
import time
import uuid
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ConversationStorage:
    """Class to handle storing and retrieving conversation history."""
    
    def __init__(self, storage_dir='conversation_history'):
        """Initialize the conversation storage.
        
        Args:
            storage_dir (str): Directory to store conversation history files.
        """
        self.storage_dir = storage_dir
        
        # Create storage directory if it doesn't exist
        if not os.path.exists(storage_dir):
            os.makedirs(storage_dir)
        
        # Path to the index file that contains metadata about all conversations
        self.index_path = os.path.join(storage_dir, 'index.json')
        
        # Path to the manual intent data file
        self.manual_intent_data_path = os.path.join(storage_dir, 'manual_intent_data.json')
        
        # Initialize or load the index
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, 'r') as f:
                    self.index = json.load(f)
            except json.JSONDecodeError:
                logger.error(f"Error loading conversation index from {self.index_path}")
                self.index = {'conversations': []}
        else:
            self.index = {'conversations': []}
            
        # Initialize or load the manual intent data
        if os.path.exists(self.manual_intent_data_path):
            try:
                with open(self.manual_intent_data_path, 'r') as f:
                    self.manual_intent_data = json.load(f)
            except json.JSONDecodeError:
                logger.error(f"Error loading manual intent data from {self.manual_intent_data_path}")
                self.manual_intent_data = {}
        else:
            self.manual_intent_data = {}
    
    def save_conversation(self, conversation_data, metadata):
        """Save a conversation to storage.
        
        Args:
            conversation_data (dict): The conversation data including messages.
            metadata (dict): Metadata about the conversation (flow_id, intent, type, etc.).
            
        Returns:
            str: The ID of the saved conversation.
        """
        # Generate a unique ID for the conversation
        conversation_id = str(uuid.uuid4())
        
        # Add timestamp
        timestamp = time.time()
        date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        
        # Create the conversation record
        conversation_record = {
            'id': conversation_id,
            'timestamp': timestamp,
            'date': date_str,
            'metadata': metadata,
            'summary': self._generate_summary(conversation_data)
        }
        
        # Add to index
        self.index['conversations'].append(conversation_record)
        
        # Save the index
        with open(self.index_path, 'w') as f:
            json.dump(self.index, f, indent=2)
        
        # Save the full conversation data to a separate file
        conversation_path = os.path.join(self.storage_dir, f"{conversation_id}.json")
        with open(conversation_path, 'w') as f:
            json.dump({
                'id': conversation_id,
                'timestamp': timestamp,
                'date': date_str,
                'metadata': metadata,
                'conversation': conversation_data
            }, f, indent=2)
        
        return conversation_id
    
    def get_conversation_list(self, sort_by='timestamp', sort_order='desc', limit=None, offset=0, filters=None):
        """Get a list of conversations with optional sorting, pagination, and filtering.
        
        Args:
            sort_by (str): Field to sort by ('timestamp', 'flow_id', etc.).
            sort_order (str): Sort order ('asc' or 'desc').
            limit (int, optional): Maximum number of conversations to return.
            offset (int): Number of conversations to skip.
            filters (dict, optional): Filters to apply (e.g., {'type': 'manual'}).
            
        Returns:
            list: List of conversation records (without full message data).
        """
        conversations = self.index['conversations']
        
        # Apply filters
        if filters:
            filtered_conversations = []
            for conv in conversations:
                match = True
                for key, value in filters.items():
                    if key in conv['metadata'] and conv['metadata'][key] != value:
                        match = False
                        break
                if match:
                    filtered_conversations.append(conv)
            conversations = filtered_conversations
        
        # Sort
        if sort_by == 'timestamp':
            conversations.sort(key=lambda x: x['timestamp'], reverse=(sort_order == 'desc'))
        elif sort_by in ['flow_id', 'intent', 'type']:
            conversations.sort(key=lambda x: x['metadata'].get(sort_by, ''), reverse=(sort_order == 'desc'))
        
        # Apply pagination
        if limit is not None:
            conversations = conversations[offset:offset + limit]
        else:
            conversations = conversations[offset:]
        
        return conversations
    
    def get_conversation(self, conversation_id):
        """Get a specific conversation by ID.
        
        Args:
            conversation_id (str): The ID of the conversation to retrieve.
            
        Returns:
            dict: The conversation data, or None if not found.
        """
        conversation_path = os.path.join(self.storage_dir, f"{conversation_id}.json")
        
        if not os.path.exists(conversation_path):
            return None
        
        try:
            with open(conversation_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Error loading conversation from {conversation_path}")
            return None
            
    def save_evaluation(self, conversation_id, evaluation):
        """Save an evaluation for a specific conversation.
        
        Args:
            conversation_id (str): The ID of the conversation to save the evaluation for.
            evaluation (str): The evaluation text.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        conversation_path = os.path.join(self.storage_dir, f"{conversation_id}.json")
        
        if not os.path.exists(conversation_path):
            return False
        
        try:
            # Load the conversation
            with open(conversation_path, 'r') as f:
                conversation = json.load(f)
            
            # Add the evaluation
            conversation['evaluation'] = {
                'text': evaluation,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Save the updated conversation
            with open(conversation_path, 'w') as f:
                json.dump(conversation, f, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"Error saving evaluation: {str(e)}")
            return False
            
    def get_evaluation(self, conversation_id):
        """Get the evaluation for a specific conversation.
        
        Args:
            conversation_id (str): The ID of the conversation to get the evaluation for.
            
        Returns:
            dict: The evaluation data, or None if not found.
        """
        conversation = self.get_conversation(conversation_id)
        
        if not conversation or 'evaluation' not in conversation:
            return None
        
        return conversation['evaluation']
    
    def delete_conversation(self, conversation_id):
        """Delete a conversation.
        
        Args:
            conversation_id (str): The ID of the conversation to delete.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        # Remove from index
        self.index['conversations'] = [c for c in self.index['conversations'] if c['id'] != conversation_id]
        
        # Save the updated index
        with open(self.index_path, 'w') as f:
            json.dump(self.index, f, indent=2)
        
        # Delete the conversation file
        conversation_path = os.path.join(self.storage_dir, f"{conversation_id}.json")
        if os.path.exists(conversation_path):
            os.remove(conversation_path)
            return True
        
        return False
    
    def _generate_summary(self, conversation_data):
        """Generate a summary of the conversation.
        
        Args:
            conversation_data (dict): The conversation data.
            
        Returns:
            dict: A summary of the conversation.
        """
        messages = conversation_data.get('messages', [])
        message_count = len(messages)
        
        # Get first and last messages for preview
        first_message = messages[0]['content'] if message_count > 0 else ""
        last_message = messages[-1]['content'] if message_count > 0 else ""
        
        # Truncate messages for preview
        max_preview_length = 50
        if len(first_message) > max_preview_length:
            first_message = first_message[:max_preview_length] + "..."
        if len(last_message) > max_preview_length:
            last_message = last_message[:max_preview_length] + "..."
        
        return {
            'message_count': message_count,
            'first_message': first_message,
            'last_message': last_message
        }

    def save_manual_intent_data(self, flow_id, manual_intent_data):
        """Save manual intent data for a specific flow ID.
        
        Args:
            flow_id (str): The flow ID to save the manual intent data for.
            manual_intent_data (dict): The manual intent data.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            # Add the manual intent data to the dictionary
            self.manual_intent_data[flow_id] = manual_intent_data
            
            # Save the updated manual intent data
            with open(self.manual_intent_data_path, 'w') as f:
                json.dump(self.manual_intent_data, f, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"Error saving manual intent data: {str(e)}")
            return False
    
    def get_manual_intent_data(self, flow_id):
        """Get manual intent data for a specific flow ID.
        
        Args:
            flow_id (str): The flow ID to get the manual intent data for.
            
        Returns:
            dict: The manual intent data, or None if not found.
        """
        return self.manual_intent_data.get(flow_id)