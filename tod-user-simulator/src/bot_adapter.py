import logging
from functools import wraps
import time


class IntentLoadingError(Exception):
    """Exception raised when intents cannot be loaded."""
    pass

from langchain.prompts import PromptTemplate
from langchain_aws import ChatBedrock
from nlu_api_framework import NluAPIFramework
from prompts import CONV_PROMPT
from safe.conf import start_botflow_session, send_botflow_turn_event, get_nlu_info_from_flow

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BotAdapter:
    """Adapter class to interface with the bot functionality from main.py."""
    
    def __init__(self, flow_id, org_id='3893d439-310d-47fe-a218-93823ad044a5',
                 base_url='https://language-understanding-service.prv-use1-ai.dev-pure.cloud', intent=None,
                 manual_intent_data=None):
        """Initialize the bot adapter with a flow ID and optional intent.
        
        Args:
            flow_id (str): The UUID of the flow to use.
            intent (str, optional): The intent to test. If not provided, will use the first intent from the API.
            manual_intent_data (dict, optional): Manual intent data provided by the user when intents cannot be loaded.
                Expected format: {'bot_functions': ['function1', 'function2', ...], 'test_functionality': 'specific functionality'}
        """
        self.flow_id = flow_id
        self.org_id = org_id
        self.base_url = base_url
        self.using_manual_intents = manual_intent_data is not None
        
        # If manual intent data is provided, use it instead of loading from API
        if self.using_manual_intents:
            self.intent_list = {}
            self.slot_list = {}
            
            # Create an intent list from the bullet points
            for i, function in enumerate(manual_intent_data['bot_functions']):
                intent_name = f"intent_{i+1}"
                self.intent_list[intent_name] = function
            
            # Set the current intent to the test functionality
            self.current_intent = manual_intent_data['test_functionality']
            
            # Skip the API calls
            self.domain_id = None
            self.version_id = None
            self.version_deets = None
        else:
            try:
                # Try to load intents from API
                self.domain_id, self.version_id = get_nlu_info_from_flow(self.flow_id)
                
                self.nlu_api = NluAPIFramework(self.org_id, self.base_url)
                self.version_deets = self.nlu_api.show_domain_version_details(self.domain_id, self.version_id)[1]
                
                # Process intent and slot lists
                self.intent_list = {}
                self.slot_list = {}
                for intent_data in self.version_deets['intents']:
                    self.intent_list[intent_data['name']] = intent_data['description'] if 'description' in intent_data else \
                        f"This is a generic description for the intent {intent_data['name']}"
                    if 'entityNameReferences' not in intent_data:
                        continue
                    for slot in intent_data['entityNameReferences']:
                        if slot in self.slot_list:
                            self.slot_list[slot].append(intent_data['name'])
                        else:
                            self.slot_list[slot] = [intent_data['name']]

                if not self.intent_list:
                    # If no intents are found, raise an IntentLoadingError
                    logger.error("No intents found for this bot")
                    raise IntentLoadingError("No intents found for this bot")
                elif intent and intent in self.intent_list: # Set the intent to use
                    self.current_intent = intent
                else:
                    # Use the first intent if none provided or invalid
                    self.current_intent = list(self.intent_list.keys())[0]
                    if intent and intent not in self.intent_list:
                        logger.warning(f"Intent '{intent}' not found. Using '{self.current_intent}' instead.")
            except Exception as e:
                # If loading intents fails, raise an exception with a specific error code
                logger.error(f"Failed to load intents: {str(e)}")
                raise IntentLoadingError(f"Failed to load intents: {str(e)}")
        
        # Initialize conversation
        self.conv_history = []
        self.session_id = None
        self.previous_turn_id = None
        self.expected_action = None
        self.end_convo = False
    
    def start_conversation(self):
        """Start a new conversation session.
        
        Returns:
            str: The initial bot message.
        """
        try:
            self.session_id, bot_response, self.expected_action, self.previous_turn_id = start_botflow_session(self.flow_id)
            self.conv_history.append(f'AGENT: {bot_response}')
            return bot_response
        except Exception as e:
            logger.error(f"Error starting conversation: {str(e)}")
            raise
    
    def send_message(self, user_message):
        """Send a message to the bot and get the response.
        
        Args:
            user_message (str): The message to send.
            
        Returns:
            dict: A dictionary containing the bot's response and conversation status.
        """
        if self.end_convo:
            self.end_conversation()
            return {
                "status": "error",
                "error": "Conversation has already ended",
                "conversation_ended": True
            }
        
        try:
            # If user provided a message, use it directly
            if user_message:
                response = send_botflow_turn_event(
                    self.session_id, 
                    'USER_INPUT', 
                    text=user_message, 
                    previous_turn_id=self.previous_turn_id
                )
            else:
                # Otherwise, generate a message using Claude
                example = self.get_claude_response(
                    prompt_string=CONV_PROMPT,
                    prompt_params={
                        'intent_list': str(self.intent_list),
                        'slot_list': str(self.slot_list),
                        'current_intent': self.current_intent,
                        "conv_history": '\n'.join(self.conv_history)
                    },
                    model_id='anthropic.claude-3-5-sonnet-20240620-v1:0'
                )
                
                user_message = example.content
                
                response = send_botflow_turn_event(
                    self.session_id, 
                    'USER_INPUT', 
                    text=user_message, 
                    previous_turn_id=self.previous_turn_id
                )
            
            try:
                agent_response = response['prompts']['textPrompts']['segments'][0].get('text', '')
                self.expected_action = response['nextActionType']
                self.previous_turn_id = response['id']
            except KeyError:
                logger.error(f"Unexpected response format: {response}")
                return {
                    "status": "error",
                    "error": "Unexpected response format from bot",
                    "conversation_ended": True
                }
            
            # Update conversation history
            self.conv_history.append(f"USER: {user_message}")
            self.conv_history.append(f"AGENT: {agent_response}")
            
            # Check if conversation has ended
            if self.expected_action == 'NoOp':
                self.end_convo = True
            
            return {
                "status": "success",
                "message": agent_response,
                "user_message": user_message,
                "conversation_ended": self.end_convo
            }
            
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "conversation_ended": False
            }
    
    @staticmethod
    def retry(max_retries=3, retry_delay=5):
        """Decorator to retry a function if it raises an exception."""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                retries = 0
                while retries < max_retries:
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        retries += 1
                        logger.warning(f"Retrying {func.__name__} due to exception: {e}")
                        time.sleep(retry_delay)
                else:
                    raise Exception(f"Maximum retries ({max_retries}) exceeded for {func.__name__}")
            return wrapper
        return decorator
    
    @retry(max_retries=3, retry_delay=5)
    def get_claude_response(
        self,
        prompt_string,
        prompt_params,
        model_id="anthropic.claude-3-haiku-20240307-v1:0",
        model_kwargs={
            "max_tokens": 200,
            "temperature": 1.0,
            "top_p": 1,
            "stop_sequences": ['User:', '</assistant>'],
        },
    ):
        """Get a response from Claude."""
        model = ChatBedrock(
            region_name="us-east-1",
            model_id=model_id,
            model_kwargs=model_kwargs
        )
        prompt = PromptTemplate.from_template(prompt_string)
        chain = prompt | model
        return chain.invoke(prompt_params)
    
    def get_available_intents(self):
        """Get a list of available intents.
        
        Returns:
            dict: A dictionary of intent names and descriptions.
            
        Raises:
            IntentLoadingError: If intents cannot be loaded or if the intent list is empty.
        """
        if (not self.intent_list or len(self.intent_list) == 0) and not self.using_manual_intents:
            raise IntentLoadingError("No intents available for this bot")
            
        return self.intent_list
        
    def auto_conversation_step(self):
        """Perform one step of an automated conversation using the LLM.
        
        Returns:
            dict: A dictionary containing the user message, bot response, and conversation status.
        """
        if self.end_convo:
            return {
                "status": "error",
                "error": "Conversation has already ended",
                "conversation_ended": True
            }
            
        try:
            # Generate user message using Claude
            example = self.get_claude_response(
                prompt_string=CONV_PROMPT,
                prompt_params={
                    'intent_list': str(self.intent_list),
                    'slot_list': str(self.slot_list),
                    'current_intent': self.current_intent,
                    "conv_history": '\n'.join(self.conv_history)
                },
                model_id='anthropic.claude-3-5-sonnet-20240620-v1:0'
            )
            
            user_message = example.content
            
            # Send the generated message to the bot
            response = send_botflow_turn_event(
                self.session_id, 
                'USER_INPUT', 
                text=user_message, 
                previous_turn_id=self.previous_turn_id
            )
            
            try:
                if response['prompts']['textPrompts']['segments'][0].get('type', '') == 'MessageEvent':
                    self.previous_turn_id = response['id']
                    return self.auto_conversation_step()
                agent_response = response['prompts']['textPrompts']['segments'][0]['text']
                self.expected_action = response['nextActionType']
                self.previous_turn_id = response['id']
            except KeyError:
                if response.get('code', '') == 'session.already.closed':
                    self.end_convo = True
                    return {
                        "status": "error",
                        "error": "Conversation has already ended. Agent has escalated.",
                        "conversation_ended": True
                    }
                logger.error(f"Unexpected response format: {response}")
                return {
                    "status": "error",
                    "error": "Unexpected response format from bot",
                    "conversation_ended": True
                }
            
            # Update conversation history
            self.conv_history.append(f"USER: {user_message}")
            self.conv_history.append(f"AGENT: {agent_response}")
            
            # Check if conversation has ended
            if self.expected_action == 'NoOp':
                self.end_convo = True
            
            return {
                "status": "success",
                "user_message": user_message,
                "bot_message": agent_response,
                "conversation_ended": self.end_convo
            }
            
        except Exception as e:
            logger.error(f"Error in auto conversation step: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "conversation_ended": False
            }

    def end_conversation(self):
        send_botflow_turn_event(self.session_id, 'USER_DISCONNECT', previous_turn_id=self.previous_turn_id)