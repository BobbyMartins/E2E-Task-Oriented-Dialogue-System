from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import uuid
import os
import logging
from datetime import datetime
from bot_adapter import BotAdapter, IntentLoadingError
from conversation_storage import ConversationStorage
from safe.conf import search_for_botflow
from prompts import EVALUATE_CHAT_PROMPT

# TOD Simulator imports
try:
    from session_manager import SessionManager, SessionStatus
    from model_router import ModelRouter
    TOD_AVAILABLE = True
except ImportError as e:
    print(f"TOD components not available: {e}")
    TOD_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)  # Set a secret key for session management

# Initialize conversation storage
conversation_storage = ConversationStorage()

# Initialize TOD components if available
if TOD_AVAILABLE:
    session_manager = SessionManager()
    model_router = ModelRouter()
else:
    session_manager = None
    model_router = None

# Domain configurations for TOD simulator
DOMAIN_CONFIGS = {
    "hotel": {
        "name": "hotel",
        "description": "You are a helpful hotel assistant, your job is to help users in whatever queries they may have.",
        "intent_list": {
            "book_room": "The user wants to book a room in the hotel",
            "cancel_booking": "The user wants to cancel an existing booking",
            "general_enquiries": "The user wants to ask general questions about the hotel",
            "chit_chat": "Queries outside of the other intents specified. Apart from greetings and hellos, the response for this one should be 'Sorry, I can only help you with hotel queries.'"
        },
        "slots_to_fill": {
            "dateFrom": ["book_room"],
            "dateTo": ["book_room"],
            "bookingID": ["cancel_booking"]
        },
        "action_slot_pair": {
            "makeBooking": ["dateFrom", "dateTo"],
            "lookUpBooking": ["bookingID"],
            "cancellation": ["bookingID"]
        }
    },
    "restaurant": {
        "name": "restaurant",
        "description": "You are a helpful restaurant assistant, your job is to help users with reservations and inquiries.",
        "intent_list": {
            "make_reservation": "The user wants to make a restaurant reservation",
            "cancel_reservation": "The user wants to cancel an existing reservation",
            "menu_inquiry": "The user wants to ask about menu items or dietary options",
            "chit_chat": "Queries outside of the other intents specified. Apart from greetings and hellos, the response for this one should be 'Sorry, I can only help you with restaurant queries.'"
        },
        "slots_to_fill": {
            "date": ["make_reservation"],
            "time": ["make_reservation"],
            "party_size": ["make_reservation"],
            "reservationID": ["cancel_reservation"]
        },
        "action_slot_pair": {
            "makeReservation": ["date", "time", "party_size"],
            "cancelReservation": ["reservationID"],
            "checkAvailability": ["date", "time"]
        }
    },
    "flight": {
        "name": "flight",
        "description": "You are a helpful flight booking assistant, your job is to help users with flight bookings and travel inquiries.",
        "intent_list": {
            "book_flight": "The user wants to book a flight",
            "cancel_booking": "The user wants to cancel an existing flight booking",
            "flight_status": "The user wants to check flight status or information",
            "chit_chat": "Queries outside of the other intents specified. Apart from greetings and hellos, the response for this one should be 'Sorry, I can only help you with flight queries.'"
        },
        "slots_to_fill": {
            "departure_city": ["book_flight"],
            "arrival_city": ["book_flight"],
            "departure_date": ["book_flight"],
            "return_date": ["book_flight"],
            "bookingID": ["cancel_booking", "flight_status"]
        },
        "action_slot_pair": {
            "searchFlights": ["departure_city", "arrival_city", "departure_date"],
            "bookFlight": ["departure_city", "arrival_city", "departure_date"],
            "cancelBooking": ["bookingID"],
            "checkStatus": ["bookingID"]
        }
    }
}


@app.route("/")
def index():
    """Render the home page with the form to input flow ID and select intent."""
    # Check if we have manual intents saved in the session
    manual_intents_saved = session.get("manual_intents_saved")
    
    # Clear any existing session data if we don't have manual intents saved
    if not manual_intents_saved:
        session.clear()

    # Default flow ID for convenience
    default_flow_id = "a260b009-1fe7-4785-921d-86b44f74cf63"

    # Try to get available intents
    available_intents = {}
    intent_loading_error = False
    pending_flow_id = None
    manual_intent_data = None
    
    # Check if we have manual intents saved in the session
    if session.get("manual_intents_saved") and "flow_id" in session and "manual_intent_data" in session:
        flow_id = session["flow_id"]
        manual_intent_data = session["manual_intent_data"]
        
        # Use the test_functionality as the intent name
        test_functionality = manual_intent_data["test_functionality"]
        available_intents = {test_functionality: "Manual intent from test functionality"}
        
        # Set the selected intent to the test_functionality
        session["intent"] = test_functionality
        
        default_flow_id = flow_id  # Use the saved flow ID as the default
    else:
        try:
            # Initialize bot adapter with default flow ID
            bot = BotAdapter(flow_id=default_flow_id)
            available_intents = bot.get_available_intents()
        except IntentLoadingError as e:
            logger.warning(f"Could not get available intents: {str(e)}")
            intent_loading_error = True
            pending_flow_id = default_flow_id
        except Exception as e:
            logger.warning(f"Could not get available intents: {str(e)}")

    # Get the bot name if available
    bot_name = session.get("bot_name", "")
    
    # Get the selected intent if available
    selected_intent = session.get("intent", "")
    
    return render_template(
        "index.html",
        default_flow_id=default_flow_id,
        available_intents=available_intents,
        intent_loading_error=intent_loading_error,
        pending_flow_id=pending_flow_id,
        manual_intent_data=manual_intent_data,
        bot_name=bot_name,
        selected_intent=selected_intent
    )


@app.route("/chat", methods=["POST"])
def chat():
    """Initialize the chat session and render the chat interface."""
    try:
        # Get form data
        flow_id = request.form.get("flow_id")
        intent = request.form.get("intent")

        # Validate flow_id as UUID
        try:
            uuid_obj = uuid.UUID(flow_id)
            if str(uuid_obj) != flow_id:
                raise ValueError("Invalid UUID format")
        except (ValueError, AttributeError):
            return render_template(
                "index.html", error="Please enter a valid UUID for the flow ID"
            )

        # Check if we're using manual intents
        if intent == "manual_intents" and "manual_intent_data" in session:
            # Use the manual intent data from the session
            manual_intent_data = session["manual_intent_data"]
            bot = BotAdapter(flow_id=flow_id, manual_intent_data=manual_intent_data)
            session["using_manual_intents"] = True
        else:
            # Initialize bot adapter
            try:
                bot = BotAdapter(flow_id=flow_id, intent=intent)
            except IntentLoadingError as e:
                # Check if we have saved manual intent data for this flow ID
                saved_manual_intent_data = conversation_storage.get_manual_intent_data(flow_id)
                
                if saved_manual_intent_data:
                    # Use the saved manual intent data
                    session["flow_id"] = flow_id
                    session["manual_intent_data"] = saved_manual_intent_data
                    session["using_manual_intents"] = True
                    
                    # Redirect to chat with manual intents
                    return redirect(url_for("chat_with_manual_intents"))
                else:
                    # If intents cannot be loaded and no saved data, store the flow ID in session and redirect to index with error
                    session["pending_flow_id"] = flow_id
                    return render_template(
                        "index.html", 
                        error="Could not load intents for this bot. Please provide intent information manually.",
                        intent_loading_error=True,
                        pending_flow_id=flow_id
                    )

        # Start conversation
        initial_message = bot.start_conversation()

        # Store bot in session
        session["flow_id"] = flow_id
        session["intent"] = intent
        session["session_id"] = bot.session_id
        session["previous_turn_id"] = bot.previous_turn_id
        session["expected_action"] = bot.expected_action
        session["conversation_history"] = bot.conv_history
        session["using_manual_intents"] = False
        session["chat_mode"] = "regular"  # Ensure session isolation

        # Check if we're using manual intents
        if session.get("using_manual_intents", False) and "manual_intent_data" in session:
            return render_template(
                "chat.html", 
                flow_id=flow_id, 
                intent=intent, 
                initial_message=initial_message, 
                using_manual_intents=True,
                bot_functions=session["manual_intent_data"]["bot_functions"]
            )
        else:
            return render_template(
                "chat.html", 
                flow_id=flow_id, 
                intent=intent, 
                initial_message=initial_message, 
                using_manual_intents=False
            )

    except Exception as e:
        logger.error(f"Error initializing chat: {str(e)}")
        return render_template(
            "error.html", error=f"Failed to initialize chat: {str(e)}"
        )


@app.route("/send_message", methods=["POST"])
def send_message():
    """API endpoint to send messages to the bot and get responses."""
    try:
        # Check if session exists and is not a TOD session
        if "flow_id" not in session or "session_id" not in session:
            return jsonify(
                {"status": "error", "error": "No active conversation session"}
            )
        
        # Ensure this is not a TOD session
        if session.get("chat_mode") == "tod":
            return jsonify(
                {"status": "error", "error": "Cannot use regular chat endpoint for TOD sessions"}
            )

        # Get the message from request
        data = request.get_json()
        if not data or "message" not in data:
            return jsonify({"status": "error", "error": "No message provided"})

        user_message = data["message"]

        # Initialize bot adapter with session data
        if session.get("using_manual_intents", False) and "manual_intent_data" in session:
            # Use manual intent data
            bot = BotAdapter(
                flow_id=session["flow_id"], 
                manual_intent_data=session["manual_intent_data"]
            )
        else:
            # Use regular intent data
            bot = BotAdapter(flow_id=session["flow_id"], intent=session["intent"])
            
        bot.session_id = session["session_id"]
        bot.previous_turn_id = session["previous_turn_id"]
        bot.expected_action = session["expected_action"]
        bot.conv_history = session["conversation_history"]

        # Send the message to bot
        response = bot.send_message(user_message)

        # Update session with new state
        session["previous_turn_id"] = bot.previous_turn_id
        session["expected_action"] = bot.expected_action
        session["conversation_history"] = bot.conv_history

        # If the conversation has ended, save it
        if response.get("conversation_ended", False):
            # Format messages for storage
            messages = []
            for i, msg in enumerate(bot.conv_history):
                if i == 0:  # The first message is just the bot's initial message
                    messages.append(
                        {
                            "sender": "bot",
                            "content": msg,
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        }
                    )
                else:  # Other messages are in the format "SENDER: message"
                    parts = msg.split(":", 1)
                    if len(parts) == 2:
                        sender = parts[0].strip().lower()
                        content = parts[1].strip()
                        messages.append(
                            {
                                "sender": "user" if sender == "user" else "bot",
                                "content": content,
                                "timestamp": datetime.now().strftime(
                                    "%Y-%m-%d %H:%M:%S"
                                ),
                            }
                        )
            # End conversation with botflow

            # Save conversation
            conversation_storage.save_conversation(
                {"messages": messages},
                {
                    "flow_id": session["flow_id"],
                    "intent": session["intent"],
                    "type": "manual",
                    "session_id": session["session_id"],
                },
            )

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error sending message: {str(e)}")
        return jsonify(
            {"status": "error", "error": f"Failed to send message: {str(e)}"}
        )


@app.route("/reset")
def reset():
    """Reset the conversation and redirect to the home page."""
    # Clean up TOD session if exists
    tod_session_id = session.get("tod_session_id")
    if tod_session_id and TOD_AVAILABLE:
        try:
            session_manager.end_session(tod_session_id, status=SessionStatus.ABANDONED)
            model_router.cleanup_session(tod_session_id)
        except Exception as e:
            logger.error(f"Error cleaning up TOD session during reset: {str(e)}")
    
    session.clear()
    return redirect(url_for("index"))


@app.route("/reset_manual_intents")
def reset_manual_intents():
    """Reset only the manual intents in the session."""
    if "manual_intent_data" in session:
        del session["manual_intent_data"]
    if "manual_intents_saved" in session:
        del session["manual_intents_saved"]
    if "using_manual_intents" in session:
        del session["using_manual_intents"]
    return jsonify({"status": "success"})


@app.route("/auto_conversation", methods=["POST"])
def auto_conversation():
    """Initialize an auto-conversation session and render the auto-chat interface."""
    try:
        # Get form data
        flow_id = request.form.get("flow_id")
        intent = request.form.get("intent")

        # Validate flow_id as UUID
        try:
            uuid_obj = uuid.UUID(flow_id)
            if str(uuid_obj) != flow_id:
                raise ValueError("Invalid UUID format")
        except (ValueError, AttributeError):
            return render_template(
                "index.html", error="Please enter a valid UUID for the flow ID"
            )

        # Check if we're using manual intents
        if intent == "manual_intents" and "manual_intent_data" in session:
            # Use the manual intent data from the session
            manual_intent_data = session["manual_intent_data"]
            bot = BotAdapter(flow_id=flow_id, manual_intent_data=manual_intent_data)
            session["using_manual_intents"] = True
            session["auto_conversation"] = True
        else:
            # Initialize bot adapter
            try:
                bot = BotAdapter(flow_id=flow_id, intent=intent)
            except IntentLoadingError as e:
                # Check if we have saved manual intent data for this flow ID
                saved_manual_intent_data = conversation_storage.get_manual_intent_data(flow_id)

                if saved_manual_intent_data:
                    # Use the saved manual intent data
                    session["flow_id"] = flow_id
                    session["manual_intent_data"] = saved_manual_intent_data
                    session["using_manual_intents"] = True
                    session["auto_conversation"] = True

                    # Redirect to auto chat with manual intents
                    return redirect(url_for("chat_with_manual_intents"))
                else:
                    # If intents cannot be loaded and no saved data, store the flow ID in session and redirect to index with error
                    session["pending_flow_id"] = flow_id
                    return render_template(
                        "index.html",
                        error="Could not load intents for this bot. Please provide intent information manually.",
                        intent_loading_error=True,
                        pending_flow_id=flow_id
                    )

        # Start conversation
        initial_message = bot.start_conversation()

        # Store bot in session
        session["flow_id"] = flow_id
        session["intent"] = intent
        session["session_id"] = bot.session_id
        session["previous_turn_id"] = bot.previous_turn_id
        session["expected_action"] = bot.expected_action
        session["conversation_history"] = bot.conv_history
        session["auto_conversation"] = True
        session["chat_mode"] = "auto"  # Ensure session isolation

        # Check if we're using manual intents
        if session.get("using_manual_intents", False) and "manual_intent_data" in session:
            return render_template(
                "auto_chat.html", 
                flow_id=flow_id, 
                intent=intent, 
                initial_message=initial_message,
                using_manual_intents=True,
                bot_functions=session["manual_intent_data"]["bot_functions"]
            )
        else:
            return render_template(
                "auto_chat.html",
                flow_id=flow_id,
                intent=intent,
                initial_message=initial_message,
            )

    except Exception as e:
        logger.error(f"Error initializing auto-conversation: {str(e)}")
        return render_template(
            "error.html", error=f"Failed to initialize auto-conversation: {str(e)}"
        )


@app.route("/auto_conversation_step")
def auto_conversation_step():
    """Perform one step of the auto-conversation."""
    try:
        # Check if session exists and is not a TOD session
        if "flow_id" not in session or "session_id" not in session:
            return jsonify(
                {"status": "error", "error": "No active conversation session"}
            )
        
        # Ensure this is not a TOD session
        if session.get("chat_mode") == "tod":
            return jsonify(
                {"status": "error", "error": "Cannot use auto conversation endpoint for TOD sessions"}
            )

        # Initialize bot adapter with session data
        if session.get("using_manual_intents", False) and "manual_intent_data" in session:
            # Use manual intent data
            bot = BotAdapter(
                flow_id=session["flow_id"], 
                manual_intent_data=session["manual_intent_data"]
            )
        else:
            # Use regular intent data
            bot = BotAdapter(flow_id=session["flow_id"], intent=session["intent"])
            
        bot.session_id = session["session_id"]
        bot.previous_turn_id = session["previous_turn_id"]
        bot.expected_action = session["expected_action"]
        bot.conv_history = session["conversation_history"]

        # Perform auto conversation step
        result = bot.auto_conversation_step()

        # Update session with new state
        session["previous_turn_id"] = bot.previous_turn_id
        session["expected_action"] = bot.expected_action
        session["conversation_history"] = bot.conv_history

        # If conversation has ended, save it
        if result.get("conversation_ended", False):
            # Format messages for storage
            messages = []
            for i, msg in enumerate(bot.conv_history):
                if i == 0:  # First message is just the bot's initial message
                    messages.append(
                        {
                            "sender": "bot",
                            "content": msg,
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        }
                    )
                else:  # Other messages are in format "SENDER: message"
                    parts = msg.split(":", 1)
                    if len(parts) == 2:
                        sender = parts[0].strip().lower()
                        content = parts[1].strip()
                        messages.append(
                            {
                                "sender": "user" if sender == "user" else "bot",
                                "content": content,
                                "timestamp": datetime.now().strftime(
                                    "%Y-%m-%d %H:%M:%S"
                                ),
                            }
                        )

            # Save conversation
            conversation_storage.save_conversation(
                {"messages": messages},
                {
                    "flow_id": session["flow_id"],
                    "intent": session["intent"],
                    "type": "auto",
                    "session_id": session["session_id"],
                },
            )

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in auto conversation step: {str(e)}")
        return jsonify(
            {
                "status": "error",
                "error": f"Failed to perform auto conversation step: {str(e)}",
            }
        )


@app.route("/history")
def history():
    """Show conversation history."""
    page = request.args.get("page", 1, type=int)
    limit = 10  # Number of conversations per page
    offset = (page - 1) * limit

    # Get filter parameters
    conv_type = request.args.get("type")
    flow_id = request.args.get("flow_id")
    intent = request.args.get("intent")
    sort_by = request.args.get("sort_by", "timestamp")
    sort_order = request.args.get("sort_order", "desc")

    # Build filters
    filters = {}
    if conv_type:
        filters["type"] = conv_type
    if flow_id:
        filters["flow_id"] = flow_id
    if intent:
        filters["intent"] = intent

    # Get conversations
    conversations = conversation_storage.get_conversation_list(
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
        filters=filters,
    )

    # Get total count for pagination
    total_conversations = len(
        conversation_storage.get_conversation_list(filters=filters)
    )
    total_pages = (total_conversations + limit - 1) // limit

    # Get unique flow IDs and intents for filters
    all_conversations = conversation_storage.get_conversation_list()
    unique_flow_ids = set()
    unique_intents = set()
    for conv in all_conversations:
        if "flow_id" in conv["metadata"]:
            unique_flow_ids.add(conv["metadata"]["flow_id"])
        if "intent" in conv["metadata"]:
            unique_intents.add(conv["metadata"]["intent"])

    return render_template(
        "history.html",
        conversations=conversations,
        page=page,
        total_pages=total_pages,
        conv_type=conv_type,
        flow_id=flow_id,
        intent=intent,
        sort_by=sort_by,
        sort_order=sort_order,
        unique_flow_ids=sorted(list(unique_flow_ids)),
        unique_intents=sorted(list(unique_intents)),
    )


@app.route("/conversation/<conversation_id>")
def view_conversation(conversation_id):
    """View a specific conversation."""
    conversation = conversation_storage.get_conversation(conversation_id)

    if not conversation:
        return render_template("error.html", error="Conversation not found"), 404

    return render_template("view_conversation.html", conversation=conversation)


@app.route("/conversation/<conversation_id>/delete", methods=["POST"])
def delete_conversation(conversation_id):
    """Delete a conversation."""
    success = conversation_storage.delete_conversation(conversation_id)

    if success:
        return redirect(url_for("history"))
    else:
        return render_template("error.html", error="Failed to delete conversation"), 500


@app.route("/get_flow_intents", methods=["POST"])
def get_flow_intents():
    """Get available intents for a specific flow ID."""
    try:
        flow_id = request.form.get("flow_id")
        logger.info(f"da flow {flow_id}")

        if not flow_id:
            return jsonify({"status": "error", "error": "Flow ID is required"})

        # Initialize bot adapter with the flow ID
        bot = BotAdapter(flow_id=flow_id)

        # Get available intents
        intents = bot.get_available_intents()

        return jsonify({"status": "success", "intents": intents})

    except IntentLoadingError as e:
        logger.error(f"Error loading intents: {str(e)}")
        return jsonify({"status": "error", "error": str(e), "intent_loading_error": True})
    except Exception as e:
        logger.error(f"Error getting intents: {str(e)}")
        return jsonify({"status": "error", "error": f"Failed to get intents: {str(e)}", "intent_loading_error": False})


@app.route("/search_bot", methods=["POST"])
def search_bot():
    """Search for bots by name and return results as JSON."""
    try:
        search_term = request.form.get("search_term", "")
        if not search_term:
            return jsonify({"status": "error", "error": "No search term provided"})

        # Search for bots using the existing function
        results = search_for_botflow(name=search_term)

        # Format results for the dropdown
        formatted_results = []
        for name, details in results.items():
            # Handle both old and new format of results
            if isinstance(details, dict) and "flow_id" in details:
                flow_id = details["flow_id"]
            else:
                flow_id = details

            formatted_results.append({"name": name, "flow_id": flow_id})

        return jsonify({"status": "success", "results": formatted_results})

    except Exception as e:
        logger.error(f"Error searching for bots: {str(e)}")
        return jsonify(
            {"status": "error", "error": f"Failed to search for bots: {str(e)}"}
        )


# TOD Simulator Routes

@app.route("/tod_simulator")
def tod_simulator():
    """Render the TOD simulator main interface for domain and model selection."""
    if not TOD_AVAILABLE:
        return render_template("error.html", 
                             error="TOD Simulator components are not available. Please check your installation."), 500
    
    return render_template("tod_simulator.html")


@app.route("/start_tod_session", methods=["POST"])
def start_tod_session():
    """Initialize a new TOD session and redirect to chat interface."""
    if not TOD_AVAILABLE:
        return render_template("error.html", 
                             error="TOD Simulator components are not available."), 500
    
    try:
        # Get form data
        domain = request.form.get("domain", "").strip()
        assignment_type = request.form.get("assignment_type", "random").strip()
        model_type = request.form.get("model_type", "").strip() if assignment_type == "manual" else None
        
        # Validate domain
        if not domain:
            return render_template("tod_simulator.html", 
                                 error="Please select a domain.")
        
        if domain not in DOMAIN_CONFIGS:
            return render_template("tod_simulator.html", 
                                 error=f"Invalid domain: {domain}. Available domains: {', '.join(DOMAIN_CONFIGS.keys())}")
        
        # Validate assignment type
        if assignment_type not in ["random", "manual"]:
            return render_template("tod_simulator.html", 
                                 error="Invalid assignment type.")
        
        # Validate manual model selection
        if assignment_type == "manual":
            if not model_type:
                return render_template("tod_simulator.html", 
                                     error="Please select a model for manual assignment.")
            
            available_models = model_router.get_available_models() if model_router else []
            if model_type not in available_models:
                return render_template("tod_simulator.html", 
                                     error=f"Invalid model: {model_type}. Available models: {', '.join(available_models)}")
        
        # Create new session
        tod_session = session_manager.create_session(
            domain=domain,
            model_type=model_type,
            user_id=session.get("user_id")  # Use Flask session user_id if available
        )
        
        # Get domain configuration
        domain_config = DOMAIN_CONFIGS[domain]
        
        # Initialize model session
        model_router.initialize_session(
            session_id=tod_session.session_id,
            model_type=tod_session.model_type,
            domain_config=domain_config
        )
        
        # Generate initial message based on domain
        domain_greetings = {
            "hotel": "Hello! I'm your hotel assistant. I can help you book rooms, cancel bookings, or answer general questions about our hotel. How can I assist you today?",
            "restaurant": "Hello! I'm your restaurant assistant. I can help you make reservations, cancel existing ones, or answer questions about our menu. What would you like to do?",
            "flight": "Hello! I'm your flight booking assistant. I can help you book flights, cancel bookings, or check flight status. How can I help you today?"
        }
        
        initial_message = domain_greetings.get(domain, f"Hello! I'm your {domain} assistant. How can I help you today?")
        
        # Add initial bot message to session
        tod_session.add_turn("bot", initial_message)
        
        # Store session info in Flask session with isolation
        session["tod_session_id"] = tod_session.session_id
        session["tod_domain"] = domain
        session["tod_model_type"] = tod_session.model_type
        session["tod_assignment_method"] = tod_session.assignment_method
        session["chat_mode"] = "tod"  # Ensure session isolation from regular chat
        
        # Clear any existing regular chat session data to prevent conflicts
        regular_chat_keys = ["flow_id", "intent", "session_id", "previous_turn_id", 
                           "expected_action", "conversation_history", "using_manual_intents", 
                           "auto_conversation", "manual_intent_data"]
        for key in regular_chat_keys:
            session.pop(key, None)
        
        logger.info(f"Started TOD session {tod_session.session_id} for domain {domain} with model {tod_session.model_type}")
        
        # Redirect to chat interface
        return redirect(url_for("tod_chat"))
        
    except ValueError as e:
        logger.error(f"Validation error starting TOD session: {str(e)}")
        return render_template("tod_simulator.html", 
                             error=str(e))
    except Exception as e:
        logger.error(f"Error starting TOD session: {str(e)}")
        return render_template("tod_simulator.html", 
                             error=f"Failed to start session: {str(e)}")


@app.route("/tod_chat")
def tod_chat():
    """Render the TOD chat interface."""
    if not TOD_AVAILABLE:
        return render_template("error.html", 
                             error="TOD Simulator components are not available."), 500
    
    # Check if we have an active TOD session
    tod_session_id = session.get("tod_session_id")
    if not tod_session_id:
        return redirect(url_for("tod_simulator"))
    
    # Get session from session manager
    tod_session = session_manager.get_session(tod_session_id)
    if not tod_session:
        logger.error(f"TOD session {tod_session_id} not found")
        return redirect(url_for("tod_simulator"))
    
    # Get initial message from conversation history
    initial_message = ""
    if tod_session.conversation_history:
        initial_message = tod_session.conversation_history[0].content
    
    # Get domain configuration for template
    domain_config = DOMAIN_CONFIGS.get(tod_session.domain, {})
    
    return render_template("tod_chat.html", 
                         domain=tod_session.domain,
                         model_type=tod_session.model_type,
                         assignment_method=tod_session.assignment_method,
                         initial_message=initial_message,
                         session_id=tod_session_id,
                         domain_config=domain_config)


@app.route("/tod_send_message", methods=["POST"])
def tod_send_message():
    """API endpoint to send messages in TOD chat and get responses."""
    if not TOD_AVAILABLE:
        return jsonify({"status": "error", "error": "TOD Simulator components are not available"})
    
    try:
        # Check if session exists
        tod_session_id = session.get("tod_session_id")
        if not tod_session_id:
            return jsonify({"status": "error", "error": "No active TOD session"})
        
        # Get the message from request
        data = request.get_json()
        if not data or "message" not in data:
            return jsonify({"status": "error", "error": "No message provided"})
        
        user_message = data["message"]
        
        # Get session from session manager
        tod_session = session_manager.get_session(tod_session_id)
        if not tod_session:
            return jsonify({"status": "error", "error": "TOD session not found"})
        
        # Get conversation history for context
        conversation_history = tod_session.get_conversation_text()
        
        # Get response from model router
        model_response = model_router.get_response(
            session_id=tod_session_id,
            message=user_message,
            conversation_history=conversation_history
        )
        
        # Update session with the conversation turn
        session_manager.update_session(
            session_id=tod_session_id,
            message=user_message,
            response=model_response.response_text,
            model_metadata=model_response.model_metadata,
            processing_time=model_response.processing_time
        )
        
        return jsonify({
            "status": "success",
            "message": model_response.response_text,
            "model_type": tod_session.model_type,
            "processing_time": model_response.processing_time,
            "conversation_ended": False  # TODO: Add conversation end detection
        })
        
    except Exception as e:
        logger.error(f"Error in TOD send message: {str(e)}")
        return jsonify({"status": "error", "error": f"Failed to send message: {str(e)}"})


@app.route("/tod_end_session", methods=["POST"])
def tod_end_session():
    """End the current TOD session and redirect to feedback."""
    if not TOD_AVAILABLE:
        return jsonify({"status": "error", "error": "TOD Simulator components are not available"})
    
    try:
        tod_session_id = session.get("tod_session_id")
        if not tod_session_id:
            return jsonify({"status": "error", "error": "No active TOD session"})
        
        # End the session
        success = session_manager.end_session(tod_session_id)
        if not success:
            return jsonify({"status": "error", "error": "Failed to end session"})
        
        # Clean up model router session
        model_router.cleanup_session(tod_session_id)
        
        logger.info(f"Ended TOD session {tod_session_id}")
        
        return jsonify({
            "status": "success",
            "redirect": url_for("feedback_form")
        })
        
    except Exception as e:
        logger.error(f"Error ending TOD session: {str(e)}")
        return jsonify({"status": "error", "error": f"Failed to end session: {str(e)}"})








@app.route("/submit_manual_intents", methods=["POST"])
def submit_manual_intents():
    """Submit manual intent information for a bot."""
    try:
        # Get form data
        flow_id = request.form.get("flow_id")
        bot_functions = request.form.get("bot_functions", "").strip()
        test_functionality = request.form.get("test_functionality", "").strip()
        save_for_future = request.form.get("save_for_future") == "true"
        auto_conversation = request.form.get("auto_conversation") == "true"
        bot_name = request.form.get("bot_name", "").strip()
        
        # Validate inputs
        if not flow_id or not bot_functions or not test_functionality:
            return jsonify({"status": "error", "error": "All fields are required"})
        
        # Parse bot functions
        functions_list = [func.strip() for func in bot_functions.split('\n') if func.strip()]
        
        # Create manual intent data
        manual_intent_data = {
            "bot_functions": functions_list,
            "test_functionality": test_functionality
        }
        
        # Save to session
        session["flow_id"] = flow_id
        session["manual_intent_data"] = manual_intent_data
        session["manual_intents_saved"] = True
        session["bot_name"] = bot_name
        
        # Save for future if requested
        if save_for_future:
            conversation_storage.save_manual_intent_data(flow_id, manual_intent_data)
        
        # Determine redirect URL
        if auto_conversation:
            redirect_url = url_for("auto_conversation")
        else:
            redirect_url = url_for("chat_with_manual_intents")
        
        return jsonify({
            "status": "success",
            "redirect": redirect_url
        })
        
    except Exception as e:
        logger.error(f"Error submitting manual intents: {str(e)}")
        return jsonify({"status": "error", "error": f"Failed to submit manual intents: {str(e)}"})


@app.route("/chat_with_manual_intents")
def chat_with_manual_intents():
    """Initialize chat with manual intents."""
    try:
        # Check if we have manual intent data
        if "manual_intent_data" not in session or "flow_id" not in session:
            return redirect(url_for("index"))
        
        flow_id = session["flow_id"]
        manual_intent_data = session["manual_intent_data"]
        
        # Initialize bot adapter with manual intent data
        bot = BotAdapter(flow_id=flow_id, manual_intent_data=manual_intent_data)
        
        # Start conversation
        initial_message = bot.start_conversation()
        
        # Store bot in session
        session["intent"] = manual_intent_data["test_functionality"]
        session["session_id"] = bot.session_id
        session["previous_turn_id"] = bot.previous_turn_id
        session["expected_action"] = bot.expected_action
        session["conversation_history"] = bot.conv_history
        session["using_manual_intents"] = True
        session["chat_mode"] = "regular"  # Ensure session isolation
        
        return render_template(
            "chat.html", 
            flow_id=flow_id, 
            intent=manual_intent_data["test_functionality"], 
            initial_message=initial_message,
            using_manual_intents=True,
            bot_functions=manual_intent_data["bot_functions"]
        )
        
    except Exception as e:
        logger.error(f"Error initializing chat with manual intents: {str(e)}")
        return render_template("error.html", error=f"Failed to initialize chat: {str(e)}")
    tod_session = session_manager.get_session(tod_session_id)
    if not tod_session:
        return redirect(url_for("tod_simulator"))
    
    # Get domain configuration
    domain_config = DOMAIN_CONFIGS[tod_session.domain]
    
    # Get initial message (first bot message)
    initial_message = None
    if tod_session.conversation_history:
        initial_message = tod_session.conversation_history[0].content
    
    return render_template("tod_chat.html",
                         session_id=tod_session.session_id,
                         domain=tod_session.domain,
                         model_type=tod_session.model_type,
                         assignment_method=tod_session.assignment_method,
                         domain_config=domain_config,
                         initial_message=initial_message)


def _should_end_conversation(user_message, bot_response, tod_session, turn_count):
    """
    Determine if a TOD conversation should end based on multiple criteria.
    
    Args:
        user_message: The user's latest message
        bot_response: The bot's response
        tod_session: The current TOD session
        turn_count: Number of conversation turns
    
    Returns:
        bool: True if conversation should end
    """
    # Maximum turn limit
    if turn_count >= 25:
        return True
    
    # User explicitly wants to end (use word boundaries to avoid false positives)
    import re
    end_patterns = [
        r'\bgoodbye\b', r'\bbye\b', r'\bthank you\b', r'\bthanks\b', 
        r'\bdone\b', r'\bfinished\b', r'\bthat\'s all\b', r'\bnothing else\b',
        r'\bend conversation\b', r'\bstop\b', r'\bquit\b'
    ]
    if any(re.search(pattern, user_message.lower()) for pattern in end_patterns):
        return True
    
    # Bot indicates task completion
    completion_phrases = [
        "booking confirmed", "reservation made", "flight booked",
        "your booking", "confirmation number", "reference number",
        "anything else i can help", "is there anything else"
    ]
    if any(phrase in bot_response.lower() for phrase in completion_phrases):
        return True
    
    # Domain-specific completion detection
    domain = tod_session.domain
    if domain == "hotel":
        hotel_completion = [
            "room booked", "booking cancelled", "check-in", "check-out"
        ]
        if any(phrase in bot_response.lower() for phrase in hotel_completion):
            return True
    elif domain == "restaurant":
        restaurant_completion = [
            "table reserved", "reservation confirmed", "table booked"
        ]
        if any(phrase in bot_response.lower() for phrase in restaurant_completion):
            return True
    elif domain == "flight":
        flight_completion = [
            "flight booked", "ticket confirmed", "boarding pass"
        ]
        if any(phrase in bot_response.lower() for phrase in flight_completion):
            return True
    
    # Repetitive responses (conversation stuck)
    if turn_count >= 5:
        recent_responses = [turn.content for turn in tod_session.conversation_history[-4:] 
                          if turn.sender == 'bot']
        if len(set(recent_responses)) <= 2:  # Too much repetition
            return True
    
    return False


@app.route("/tod_chat_message", methods=["POST"])
def tod_chat_message():
    """Handle TOD chat messages and return bot responses."""
    if not TOD_AVAILABLE:
        return jsonify({"status": "error", "error": "TOD Simulator not available"})
    
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "error": "No JSON data provided"})
        
        if "message" not in data:
            return jsonify({"status": "error", "error": "Missing message in request"})
        
        if "session_id" not in data:
            return jsonify({"status": "error", "error": "Missing session_id in request"})
        
        user_message = data["message"].strip()
        session_id = data["session_id"].strip()
        
        # Validate message
        if not user_message:
            return jsonify({"status": "error", "error": "Message cannot be empty"})
        
        if len(user_message) > 1000:  # Reasonable message length limit
            return jsonify({"status": "error", "error": "Message too long (max 1000 characters)"})
        
        # Get session
        tod_session = session_manager.get_session(session_id)
        if not tod_session:
            return jsonify({"status": "error", "error": "Session not found or expired"})
        
        # Check if session is still active
        if tod_session.status != SessionStatus.ACTIVE:
            return jsonify({"status": "error", "error": f"Session is {tod_session.status.value}, not active"})
        
        # Get domain configuration
        domain_config = DOMAIN_CONFIGS.get(tod_session.domain)
        if not domain_config:
            return jsonify({"status": "error", "error": f"Invalid domain configuration: {tod_session.domain}"})
        
        # Get conversation history as text
        conversation_history = tod_session.get_conversation_text()
        
        # Generate response using model router
        model_response = model_router.get_response(
            session_id=session_id,
            message=user_message,
            conversation_history=conversation_history
        )
        
        if not model_response or not model_response.response_text:
            return jsonify({"status": "error", "error": "Failed to generate response"})
        
        bot_response = model_response.response_text
        
        # Update session with new turn
        update_success = session_manager.update_session(
            session_id=session_id,
            message=user_message,
            response=bot_response,
            model_metadata=model_response.model_metadata,
            processing_time=model_response.processing_time
        )
        
        if not update_success:
            logger.warning(f"Failed to update session {session_id}")
        
        # Calculate turn count
        turn_count = len(tod_session.conversation_history)
        
        # Check if conversation should end with improved detection
        conversation_ended = _should_end_conversation(
            user_message, bot_response, tod_session, turn_count
        )
        
        logger.info(f"TOD chat turn completed for session {session_id}: {turn_count} turns, ended: {conversation_ended}")
        
        return jsonify({
            "status": "success",
            "message": bot_response,
            "conversation_ended": conversation_ended,
            "turn_count": turn_count,
            "model_type": tod_session.model_type,
            "domain": tod_session.domain
        })
        
    except Exception as e:
        logger.error(f"Error in TOD chat message: {str(e)}")
        return jsonify({"status": "error", "error": f"Failed to process message: {str(e)}"})


@app.route("/end_tod_conversation", methods=["POST"])
def end_tod_conversation():
    """End a TOD conversation session."""
    if not TOD_AVAILABLE:
        return jsonify({"status": "error", "error": "TOD Simulator not available"})
    
    try:
        data = request.get_json()
        if not data or "session_id" not in data:
            return jsonify({"status": "error", "error": "Missing session_id"})
        
        session_id = data["session_id"]
        
        # End the session
        success = session_manager.end_session(session_id, SessionStatus.COMPLETED)
        
        if success:
            return jsonify({"status": "success"})
        else:
            return jsonify({"status": "error", "error": "Session not found"})
            
    except Exception as e:
        logger.error(f"Error ending TOD conversation: {str(e)}")
        return jsonify({"status": "error", "error": f"Failed to end conversation: {str(e)}"})


@app.route("/feedback_form")
def feedback_form():
    """Render the feedback form for a completed TOD session."""
    if not TOD_AVAILABLE:
        return render_template("error.html", 
                             error="TOD Simulator components are not available."), 500
    
    session_id = request.args.get("session_id")
    if not session_id:
        return redirect(url_for("tod_simulator"))
    
    # Get session
    tod_session = session_manager.get_session(session_id)
    if not tod_session:
        return render_template("error.html", error="Session not found"), 404
    
    # Calculate conversation summary
    conversation_summary = {
        "total_turns": len(tod_session.conversation_history),
        "duration": str(tod_session.end_time - tod_session.start_time) if tod_session.end_time else "Unknown"
    }
    
    return render_template("feedback_form.html",
                         session_id=session_id,
                         domain=tod_session.domain,
                         model_type=tod_session.model_type,
                         conversation_summary=conversation_summary)


@app.route("/submit_feedback", methods=["POST"])
def submit_feedback():
    """Handle feedback form submission."""
    if not TOD_AVAILABLE:
        return jsonify({"status": "error", "error": "TOD Simulator not available"})
    
    try:
        # Get form data
        session_id = request.form.get("session_id", "").strip()
        if not session_id:
            return jsonify({"status": "error", "error": "Missing session_id"})
        
        # Get session
        tod_session = session_manager.get_session(session_id)
        if not tod_session:
            return jsonify({"status": "error", "error": "Session not found"})
        
        # Collect and validate feedback data
        try:
            feedback_data = {
                "session_id": session_id,
                "task_success_rate": int(request.form.get("task_success_rate", 0)),
                "user_satisfaction": int(request.form.get("user_satisfaction", 0)),
                "appropriateness": int(request.form.get("appropriateness", 0)),
                "naturalness": int(request.form.get("naturalness", 0)),
                "coherence": int(request.form.get("coherence", 0)),
                "efficiency": int(request.form.get("efficiency", 0)),
                "conciseness": int(request.form.get("conciseness", 0)),
                "comments": request.form.get("comments", "").strip(),
                "feedback_timestamp": datetime.now().isoformat()
            }
        except (ValueError, TypeError) as e:
            return jsonify({"status": "error", "error": f"Invalid rating values: {str(e)}"})
        
        # Validate required ratings
        required_ratings = ["task_success_rate", "user_satisfaction", "appropriateness", 
                          "naturalness", "coherence", "efficiency", "conciseness"]
        
        missing_ratings = []
        invalid_ratings = []
        
        for rating in required_ratings:
            if rating not in feedback_data or feedback_data[rating] is None:
                missing_ratings.append(rating.replace('_', ' ').title())
            elif not isinstance(feedback_data[rating], int) or feedback_data[rating] < 1 or feedback_data[rating] > 5:
                invalid_ratings.append(rating.replace('_', ' ').title())
        
        if missing_ratings:
            return jsonify({"status": "error", "error": f"Missing ratings for: {', '.join(missing_ratings)}"})
        
        if invalid_ratings:
            return jsonify({"status": "error", "error": f"Invalid ratings (must be 1-5) for: {', '.join(invalid_ratings)}"})
        
        # Validate comments length
        if len(feedback_data["comments"]) > 2000:
            return jsonify({"status": "error", "error": "Comments too long (max 2000 characters)"})
        
        # Ensure session is ended
        if tod_session.status == SessionStatus.ACTIVE:
            session_manager.end_session(session_id, SessionStatus.COMPLETED)
            tod_session = session_manager.get_session(session_id)  # Refresh session
        
        # Save feedback to conversation storage with TOD-specific format
        conversation_data = {
            "conversation_id": str(uuid.uuid4()),
            "session_id": session_id,
            "domain": tod_session.domain,
            "model_type": tod_session.model_type,
            "start_time": tod_session.start_time.isoformat(),
            "end_time": tod_session.end_time.isoformat() if tod_session.end_time else datetime.now().isoformat(),
            "conversation": {
                "messages": [
                    {
                        "sender": turn.sender,
                        "content": turn.content,
                        "timestamp": turn.timestamp.isoformat(),
                        "turn_number": turn.turn_number
                    }
                    for turn in tod_session.conversation_history
                ]
            },
            "domain_config": DOMAIN_CONFIGS[tod_session.domain],
            "feedback": feedback_data,
            "metadata": {
                "total_turns": len(tod_session.conversation_history),
                "completion_status": "completed",
                "assignment_method": tod_session.assignment_method,
                "average_rating": sum([
                    feedback_data["task_success_rate"],
                    feedback_data["user_satisfaction"],
                    feedback_data["appropriateness"],
                    feedback_data["naturalness"],
                    feedback_data["coherence"],
                    feedback_data["efficiency"],
                    feedback_data["conciseness"]
                ]) / 7.0
            }
        }
        
        # Save to conversation storage
        conversation_id = conversation_storage.save_conversation(
            conversation_data["conversation"],
            {
                "flow_id": "tod_simulator",
                "intent": tod_session.domain,
                "type": "tod",
                "session_id": session_id,
                "model_type": tod_session.model_type,
                "domain": tod_session.domain,
                "feedback": feedback_data,
                "tod_data": conversation_data
            }
        )
        
        logger.info(f"Feedback submitted for TOD session {session_id}, saved as conversation {conversation_id}")
        
        return jsonify({
            "status": "success",
            "message": "Feedback submitted successfully",
            "redirect": url_for("feedback_summary", session_id=session_id)
        })
        
    except Exception as e:
        logger.error(f"Error submitting feedback: {str(e)}")
        return jsonify({"status": "error", "error": f"Failed to submit feedback: {str(e)}"})


@app.route("/feedback_summary/<session_id>")
def feedback_summary(session_id):
    """Display post-feedback conversation summary."""
    if not TOD_AVAILABLE:
        return render_template("error.html", 
                             error="TOD Simulator components are not available."), 500
    
    try:
        # Get session
        tod_session = session_manager.get_session(session_id)
        if not tod_session:
            return render_template("error.html", error="Session not found"), 404
        
        # Get conversation from storage (should have feedback now)
        conversations = conversation_storage.get_conversation_list(
            filters={"session_id": session_id, "type": "tod"}
        )
        
        conversation_data = None
        if conversations:
            conversation_data = conversations[0]
        
        # Calculate summary statistics
        summary_stats = {
            "total_turns": len(tod_session.conversation_history),
            "user_turns": len([t for t in tod_session.conversation_history if t.sender == 'user']),
            "bot_turns": len([t for t in tod_session.conversation_history if t.sender == 'bot']),
            "duration": str(tod_session.end_time - tod_session.start_time) if tod_session.end_time else "Unknown",
            "domain": tod_session.domain,
            "model_type": tod_session.model_type,
            "assignment_method": tod_session.assignment_method,
            "completion_status": tod_session.status.value
        }
        
        # Get feedback data if available
        feedback_data = None
        if conversation_data and "feedback" in conversation_data.get("metadata", {}):
            feedback_data = conversation_data["metadata"]["feedback"]
        
        return render_template("feedback_summary.html",
                             session_id=session_id,
                             summary_stats=summary_stats,
                             feedback_data=feedback_data,
                             conversation_data=conversation_data)
        
    except Exception as e:
        logger.error(f"Error displaying feedback summary: {str(e)}")
        return render_template("error.html", error=f"Failed to load summary: {str(e)}"), 500


@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors."""
    return render_template("error.html", error="Page not found"), 404


@app.route('/conversation/<conversation_id>/evaluate', methods=['POST'])
def evaluate_conversation(conversation_id):
    """Evaluate a conversation using the LLM."""
    try:
        # Get the conversation
        conversation = conversation_storage.get_conversation(conversation_id)
        
        if not conversation:
            return jsonify({
                "status": "error",
                "error": "Conversation not found"
            })
        
        # Check if evaluation already exists
        existing_evaluation = conversation_storage.get_evaluation(conversation_id)
        if existing_evaluation:
            return jsonify({
                "status": "success",
                "evaluation": existing_evaluation['text'],
                "timestamp": existing_evaluation['timestamp'],
                "cached": True
            })
        
        # Initialize bot adapter with the flow ID from the conversation
        flow_id = conversation['metadata']['flow_id']
        intent = conversation['metadata']['intent']
        
        # Check if we have saved manual intent data for this flow ID
        saved_manual_intent_data = conversation_storage.get_manual_intent_data(flow_id)
        
        if saved_manual_intent_data:
            # Use the saved manual intent data
            bot = BotAdapter(flow_id=flow_id, manual_intent_data=saved_manual_intent_data)
        else:
            # Use regular intent data
            bot = BotAdapter(flow_id=flow_id, intent=intent)
        
        # Format the conversation history for the evaluation prompt
        conv_history = []
        for message in conversation['conversation']['messages']:
            sender = "USER" if message['sender'] == "user" else "AGENT"
            conv_history.append(f"{sender}: {message['content']}")
        
        # Get the evaluation from Claude
        evaluation = bot.get_claude_response(
            prompt_string=EVALUATE_CHAT_PROMPT,
            prompt_params={
                'intent_list': str(bot.intent_list),
                'slot_list': str(bot.slot_list),
                'current_intent': intent,
                "conv_history": '\n'.join(conv_history)
            },
            model_id='anthropic.claude-3-5-sonnet-20240620-v1:0',
            model_kwargs={
                "max_tokens": 1000,
                "temperature": 0.7,
                "top_p": 0.9,
            }
        )
        
        # Save the evaluation
        evaluation_text = evaluation.content
        conversation_storage.save_evaluation(conversation_id, evaluation_text)
        
        return jsonify({
            "status": "success",
            "evaluation": evaluation_text,
            "cached": False
        })
    
    except Exception as e:
        logger.error(f"Error evaluating conversation: {str(e)}")
        return jsonify({
            "status": "error",
            "error": f"Failed to evaluate conversation: {str(e)}"
        })

@app.route("/tod_analytics")
def tod_analytics():
    """Render the TOD analytics dashboard with summary statistics and visualizations."""
    if not TOD_AVAILABLE:
        return render_template("error.html", 
                             error="TOD Simulator components are not available."), 500
    
    try:
        # Import TOD storage
        from tod_conversation_storage import TODConversationStorage
        tod_storage = TODConversationStorage()
        
        # Get filter parameters from request
        filters = {}
        if request.args.get('model_type'):
            filters['model_type'] = request.args.get('model_type')
        if request.args.get('domain'):
            filters['domain'] = request.args.get('domain')
        if request.args.get('status'):
            filters['status'] = request.args.get('status')
        if request.args.get('has_feedback'):
            filters['has_feedback'] = request.args.get('has_feedback').lower() == 'true'
        if request.args.get('date_from'):
            from datetime import datetime
            date_from = datetime.strptime(request.args.get('date_from'), '%Y-%m-%d')
            filters['date_from'] = date_from.timestamp()
        if request.args.get('date_to'):
            from datetime import datetime
            date_to = datetime.strptime(request.args.get('date_to'), '%Y-%m-%d')
            # Set to end of day
            date_to = date_to.replace(hour=23, minute=59, second=59)
            filters['date_to'] = date_to.timestamp()
        
        # Get filtered conversations
        conversations = tod_storage.get_conversations_by_filters(filters) if filters else tod_storage.tod_index['conversations']
        
        # Calculate summary statistics
        summary_stats = tod_storage.get_feedback_summary(filters)
        
        # Add completion rate to summary stats
        completed_conversations = len([c for c in conversations if c['status'] == 'completed'])
        summary_stats['completion_rate'] = completed_conversations / len(conversations) if conversations else 0
        
        # Get model comparison statistics
        model_comparison = tod_storage.get_model_comparison_stats()
        
        # Calculate distributions for charts
        domain_distribution = {}
        model_distribution = {}
        status_distribution = {}
        
        for conv in conversations:
            # Domain distribution
            domain = conv['domain']
            domain_distribution[domain] = domain_distribution.get(domain, 0) + 1
            
            # Model distribution
            model = conv['model_type']
            model_distribution[model] = model_distribution.get(model, 0) + 1
            
            # Status distribution
            status = conv['status']
            status_distribution[status] = status_distribution.get(status, 0) + 1
        
        return render_template(
            "tod_analytics.html",
            summary_stats=summary_stats,
            model_comparison=model_comparison,
            domain_distribution=domain_distribution,
            model_distribution=model_distribution,
            status_distribution=status_distribution,
            conversations=conversations
        )
        
    except Exception as e:
        logger.error(f"Error loading TOD analytics: {str(e)}")
        return render_template("error.html", 
                             error=f"Failed to load analytics: {str(e)}"), 500


@app.route("/export_tod_data")
def export_tod_data():
    """Export TOD conversation data in JSON or CSV format."""
    if not TOD_AVAILABLE:
        return render_template("error.html", 
                             error="TOD Simulator components are not available."), 500
    
    try:
        # Import TOD storage
        from tod_conversation_storage import TODConversationStorage
        tod_storage = TODConversationStorage()
        
        # Get export format
        export_format = request.args.get('format', 'json').lower()
        if export_format not in ['json', 'csv']:
            return jsonify({"error": "Invalid export format. Use 'json' or 'csv'."}), 400
        
        # Get filter parameters (same as analytics route)
        filters = {}
        if request.args.get('model_type'):
            filters['model_type'] = request.args.get('model_type')
        if request.args.get('domain'):
            filters['domain'] = request.args.get('domain')
        if request.args.get('status'):
            filters['status'] = request.args.get('status')
        if request.args.get('has_feedback'):
            filters['has_feedback'] = request.args.get('has_feedback').lower() == 'true'
        if request.args.get('date_from'):
            from datetime import datetime
            date_from = datetime.strptime(request.args.get('date_from'), '%Y-%m-%d')
            filters['date_from'] = date_from.timestamp()
        if request.args.get('date_to'):
            from datetime import datetime
            date_to = datetime.strptime(request.args.get('date_to'), '%Y-%m-%d')
            date_to = date_to.replace(hour=23, minute=59, second=59)
            filters['date_to'] = date_to.timestamp()
        
        # Export data
        export_path = tod_storage.export_data(format=export_format, filters=filters)
        
        # Send file for download
        from flask import send_file
        import os
        
        filename = os.path.basename(export_path)
        mimetype = 'application/json' if export_format == 'json' else 'text/csv'
        
        return send_file(
            export_path,
            as_attachment=True,
            download_name=filename,
            mimetype=mimetype
        )
        
    except Exception as e:
        logger.error(f"Error exporting TOD data: {str(e)}")
        return jsonify({"error": f"Failed to export data: {str(e)}"}), 500


@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors."""
    logger.error(f"Server error: {str(e)}")
    return render_template("error.html", error="Internal server error"), 500




if __name__ == "__main__":
    app.run(debug=True)
