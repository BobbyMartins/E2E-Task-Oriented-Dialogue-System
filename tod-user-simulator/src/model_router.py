"""
Model routing infrastructure for TOD User Simulator.

This module provides interfaces for routing requests between different TOD models
(Bedrock and GRPOTOD) and handles model-specific formatting and error handling.
"""

import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime

# Import existing functionality
from main import get_claude_response
from prompts import CONV_PROMPT

# Handle optional GRPOTOD imports
try:
    from grpotod import GRPOTODAgent
    GRPOTOD_AVAILABLE = True
except ImportError:
    GRPOTOD_AVAILABLE = False
    # Create a mock class for when GRPOTOD is not available
    class GRPOTODAgent:
        def __init__(self, *args, **kwargs):
            raise ImportError("GRPOTOD dependencies not available")
        def response(self, message):
            raise ImportError("GRPOTOD dependencies not available")

# Handle optional SageMaker GRPOTOD import
try:
    from grpotod_sagemaker import GRPOTODSageMakerAgent
    SAGEMAKER_GRPOTOD_AVAILABLE = True
except ImportError:
    SAGEMAKER_GRPOTOD_AVAILABLE = False
    # Create a mock class for when SageMaker GRPOTOD is not available
    class GRPOTODSageMakerAgent:
        def __init__(self, *args, **kwargs):
            raise ImportError("SageMaker GRPOTOD dependencies not available")
        def response(self, message):
            raise ImportError("SageMaker GRPOTOD dependencies not available")


@dataclass
class ModelResponse:
    """Standardized response format for all models."""

    response_text: str
    confidence: float = 0.0
    processing_time: float = 0.0
    model_metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.model_metadata is None:
            self.model_metadata = {}


class ModelInterface(ABC):
    """Abstract base class for model interfaces."""

    @abstractmethod
    def generate_response(
        self, message: str, domain_config: Dict, conversation_history: List[str]
    ) -> str:
        """Generate a response using the model."""
        pass

    @abstractmethod
    def initialize_session(self, domain_config: Dict) -> None:
        """Initialize a new session with domain configuration."""
        pass


class BedrockModelInterface(ModelInterface):
    """Interface for AWS Bedrock models using existing infrastructure."""

    def __init__(self, model_id: str = "anthropic.claude-3-haiku-20240307-v1:0"):
        self.model_id = model_id
        self.model_kwargs = {
            "max_tokens": 200,
            "temperature": 1.0,
            "top_p": 1,
            "stop_sequences": ["User:", "</assistant>"],
        }
        self.logger = logging.getLogger(__name__)

    def initialize_session(self, domain_config: Dict) -> None:
        """Initialize session - Bedrock is stateless so no initialization needed."""
        self.logger.info(
            f"Initialized Bedrock session for domain: {domain_config.get('name', 'unknown')}"
        )

    def generate_response(
        self, message: str, domain_config: Dict, conversation_history: List[str]
    ) -> str:
        """Generate response using Bedrock model."""
        start_time = time.time()

        try:
            # Format conversation history
            conv_history_str = "\n".join(conversation_history[-10:])  # Last 10 turns

            # Use the existing CONV_PROMPT template
            response = get_claude_response(
                prompt_string=CONV_PROMPT,
                prompt_params={
                    "intent_list": str(domain_config.get("intent_list", {})),
                    "slot_list": str(domain_config.get("slots_to_fill", {})),
                    "action_slot_pair": str(domain_config.get("action_slot_pair", {})),
                    "current_intent": (
                        list(domain_config.get("intent_list", {}).keys())[0]
                        if domain_config.get("intent_list")
                        else "general"
                    ),
                    "conv_history": conv_history_str,
                    "conv_number": len(conversation_history) // 2
                    + 1,  # Approximate conversation number
                },
                model_id=self.model_id,
                model_kwargs=self.model_kwargs,
            )

            processing_time = time.time() - start_time

            # Extract the response content
            response_text = (
                response.content if hasattr(response, "content") else str(response)
            )

            self.logger.info(f"Bedrock response generated in {processing_time:.2f}s")
            return response_text

        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(
                f"Bedrock model error after {processing_time:.2f}s: {str(e)}"
            )
            raise Exception(f"Bedrock model failed: {str(e)}")


class GRPOTODModelInterface(ModelInterface):
    """Interface for the custom GRPOTOD model (local)."""

    def __init__(self, model_path: str = "./././init_ft_000-merged"):
        self.model_path = model_path
        self.agent = None
        self.logger = logging.getLogger(__name__)

    def initialize_session(self, domain_config: Dict) -> None:
        """Initialize GRPOTOD agent with domain configuration."""
        if not GRPOTOD_AVAILABLE:
            raise Exception(
                "GRPOTOD dependencies not available. Please install required packages."
            )

        try:
            # Extract configuration for GRPOTOD
            intent_list = domain_config.get("intent_list", {})
            slots_to_fill = domain_config.get("slots_to_fill", {})
            action_slot_pair = domain_config.get("action_slot_pair", {})
            description = domain_config.get("description", "A helpful assistant")

            # Convert slots_to_fill to the format expected by GRPOTOD
            slot_list = set()
            for slot, intents in slots_to_fill.items():
                slot_list.add(slot)

            self.agent = GRPOTODAgent(
                model_path=self.model_path,
                description=description,
                intent_list=intent_list,
                slot_list=slot_list,
                action_list=action_slot_pair,
            )

            self.logger.info(
                f"Initialized GRPOTOD session for domain: {domain_config.get('name', 'unknown')}"
            )

        except Exception as e:
            self.logger.error(f"Failed to initialize GRPOTOD agent: {str(e)}")
            raise Exception(f"GRPOTOD initialization failed: {str(e)}")

    def generate_response(
        self, message: str, domain_config: Dict, conversation_history: List[str]
    ) -> str:
        """Generate response using GRPOTOD model."""
        if self.agent is None:
            raise Exception(
                "GRPOTOD agent not initialized. Call initialize_session first."
            )

        start_time = time.time()

        try:
            # Generate response using GRPOTOD agent
            dialogue_state, system_response = self.agent.response(message)

            processing_time = time.time() - start_time

            self.logger.info(f"GRPOTOD response generated in {processing_time:.2f}s")

            # Return the system response
            return (
                system_response
                if system_response
                else "I'm sorry, could you please repeat that?"
            )

        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(
                f"GRPOTOD model error after {processing_time:.2f}s: {str(e)}"
            )

            # Return fallback response
            return "I'm sorry, I'm having trouble understanding. Could you please rephrase your request?"


class GRPOTODSageMakerInterface(ModelInterface):
    """Interface for the GRPOTOD model deployed on SageMaker."""

    def __init__(self, endpoint_name: str = None, region_name: str = "us-east-1"):
        import os
        self.endpoint_name = endpoint_name or os.getenv('SAGEMAKER_ENDPOINT_NAME')
        self.region_name = region_name or os.getenv('AWS_REGION', 'us-east-1')
        self.agent = None
        self.logger = logging.getLogger(__name__)
        
        if not self.endpoint_name:
            raise ValueError("SageMaker endpoint name is required. Set SAGEMAKER_ENDPOINT_NAME environment variable or pass endpoint_name parameter.")

    def initialize_session(self, domain_config: Dict) -> None:
        """Initialize SageMaker GRPOTOD agent with domain configuration."""
        if not SAGEMAKER_GRPOTOD_AVAILABLE:
            raise Exception(
                "SageMaker GRPOTOD dependencies not available. Please install boto3 and check grpotod_sagemaker.py."
            )

        try:
            # Extract configuration for GRPOTOD
            intent_list = domain_config.get("intent_list", {})
            slots_to_fill = domain_config.get("slots_to_fill", {})
            action_slot_pair = domain_config.get("action_slot_pair", {})
            description = domain_config.get("description", "A helpful assistant")

            # Convert slots_to_fill to the format expected by GRPOTOD
            slot_list = {}
            for slot, intents in slots_to_fill.items():
                slot_list[slot] = intents

            self.agent = GRPOTODSageMakerAgent(
                endpoint_name=self.endpoint_name,
                region_name=self.region_name,
                description=description,
                intent_list=intent_list,
                slot_list=slot_list,
                action_list=action_slot_pair,
            )

            self.logger.info(
                f"Initialized SageMaker GRPOTOD session for domain: {domain_config.get('name', 'unknown')} using endpoint: {self.endpoint_name}"
            )

        except Exception as e:
            self.logger.error(f"Failed to initialize SageMaker GRPOTOD agent: {str(e)}")
            raise Exception(f"SageMaker GRPOTOD initialization failed: {str(e)}")

    def generate_response(
        self, message: str, domain_config: Dict, conversation_history: List[str]
    ) -> str:
        """Generate response using SageMaker GRPOTOD model."""
        if self.agent is None:
            raise Exception(
                "SageMaker GRPOTOD agent not initialized. Call initialize_session first."
            )

        start_time = time.time()

        try:
            # Generate response using SageMaker GRPOTOD agent
            dialogue_state, system_response = self.agent.response(message)

            processing_time = time.time() - start_time

            self.logger.info(f"SageMaker GRPOTOD response generated in {processing_time:.2f}s")

            # Return the system response
            return (
                system_response
                if system_response
                else "I'm sorry, could you please repeat that?"
            )

        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(
                f"SageMaker GRPOTOD model error after {processing_time:.2f}s: {str(e)}"
            )

            # Return fallback response
            return "I'm sorry, I'm experiencing technical difficulties with the SageMaker endpoint. Could you please try again?"


class ModelRouter:
    """Routes requests to appropriate TOD models and handles responses."""

    def __init__(self):
        self.bedrock_interface = BedrockModelInterface()
        self.grpotod_interface = GRPOTODModelInterface()
        
        # Initialize SageMaker interface if available
        try:
            self.sagemaker_grpotod_interface = GRPOTODSageMakerInterface()
            self.sagemaker_available = True
        except (ValueError, Exception) as e:
            self.sagemaker_grpotod_interface = None
            self.sagemaker_available = False
            logging.getLogger(__name__).info(f"SageMaker interface not available: {e}")
        
        self.logger = logging.getLogger(__name__)

        # Track active sessions
        self.active_sessions = {}

    def get_available_models(self) -> List[str]:
        """Get list of available model types."""
        models = ["bedrock", "grpotod"]
        if self.sagemaker_available:
            models.append("sagemaker-grpotod")
        return models

    def initialize_session(
        self, session_id: str, model_type: str, domain_config: Dict
    ) -> None:
        """Initialize a session for a specific model type."""
        if model_type not in self.get_available_models():
            raise ValueError(
                f"Unknown model type: {model_type}. Available: {self.get_available_models()}"
            )

        try:
            if model_type == "bedrock":
                self.bedrock_interface.initialize_session(domain_config)
            elif model_type == "grpotod":
                self.grpotod_interface.initialize_session(domain_config)
            elif model_type == "sagemaker-grpotod":
                if not self.sagemaker_available:
                    raise ValueError("SageMaker GRPOTOD interface is not available")
                self.sagemaker_grpotod_interface.initialize_session(domain_config)

            # Track the session
            self.active_sessions[session_id] = {
                "model_type": model_type,
                "domain_config": domain_config,
                "initialized_at": datetime.now(),
            }

            self.logger.info(
                f"Session {session_id} initialized with {model_type} model"
            )

        except Exception as e:
            self.logger.error(f"Failed to initialize session {session_id}: {str(e)}")
            raise

    def get_response(
        self, session_id: str, message: str, conversation_history: List[str]
    ) -> ModelResponse:
        """Get response from the appropriate model for the session."""
        if session_id not in self.active_sessions:
            raise ValueError(
                f"Session {session_id} not found. Initialize session first."
            )

        session_info = self.active_sessions[session_id]
        model_type = session_info["model_type"]
        domain_config = session_info["domain_config"]

        start_time = time.time()

        try:
            if model_type == "bedrock":
                response_text = self.bedrock_interface.generate_response(
                    message, domain_config, conversation_history
                )
            elif model_type == "grpotod":
                response_text = self.grpotod_interface.generate_response(
                    message, domain_config, conversation_history
                )
            elif model_type == "sagemaker-grpotod":
                response_text = self.sagemaker_grpotod_interface.generate_response(
                    message, domain_config, conversation_history
                )
            else:
                raise ValueError(f"Unknown model type: {model_type}")

            processing_time = time.time() - start_time

            return ModelResponse(
                response_text=response_text,
                confidence=1.0,  # Default confidence
                processing_time=processing_time,
                model_metadata={
                    "model_type": model_type,
                    "session_id": session_id,
                    "domain": domain_config.get("name", "unknown"),
                    "timestamp": datetime.now().isoformat(),
                },
            )

        except Exception as e:
            processing_time = time.time() - start_time
            self.logger.error(
                f"Error getting response for session {session_id}: {str(e)}"
            )

            # Return error response
            return ModelResponse(
                response_text="I'm sorry, I'm experiencing technical difficulties. Please try again.",
                confidence=0.0,
                processing_time=processing_time,
                model_metadata={
                    "model_type": model_type,
                    "session_id": session_id,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                },
            )

    def cleanup_session(self, session_id: str) -> None:
        """Clean up resources for a session."""
        if session_id in self.active_sessions:
            session_info = self.active_sessions[session_id]

            # Clean up model-specific resources if needed
            if session_info["model_type"] == "grpotod":
                # GRPOTOD agent cleanup would go here if needed
                pass
            elif session_info["model_type"] == "sagemaker-grpotod":
                # SageMaker GRPOTOD agent cleanup would go here if needed
                pass

            del self.active_sessions[session_id]
            self.logger.info(f"Session {session_id} cleaned up")

    def get_session_info(self, session_id: str) -> Optional[Dict]:
        """Get information about an active session."""
        return self.active_sessions.get(session_id)

    def list_active_sessions(self) -> List[str]:
        """Get list of active session IDs."""
        return list(self.active_sessions.keys())


# Configure logging
logging.basicConfig(level=logging.INFO)
