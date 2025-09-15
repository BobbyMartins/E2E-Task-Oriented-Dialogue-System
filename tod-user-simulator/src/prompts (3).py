GEN_PROMPT = """<{salt_tag}>
You are a data generator. OUTPUT MUST BE EXACTLY one single-line JSON array and nothing else (no explanations, no markup, no newlines). Each element is one conversation object that exactly matches the schema described below. If you cannot comply, output exactly: ["ERROR: reason"].

GENERATE the examples based on the following variables: 
- {intent_list}  : JSON array of allowed intent strings
- {slot_list}    : JSON array of allowed slot names (exact keys expected in belief_state when filled)
- {action_list}  : JSON array of allowed action strings
- {generated_samples} : integer count of how many samples have already been generated per intent
- {previous_example_hashes} : optional JSON array of short strings representing previous outputs' fingerprints (if available)

Here is some guidance of how the above variables should influence your generatations:
1. 

SCHEMA (required keys and types):
[
  {{
    "dialogue_id": string,                           // must be unique, format: <intent>_<counter>_<random8>
    "goal": string,
    "turns": [
      {{
        "utterance": string,                         // USER: concrete values for slots; SYSTEM: use <slot_name> placeholders where instructed below
        "system_response": string,                   // SYSTEM replies must NOT be verbatim repeats of the user's utterance
        "dialogue_acts": {{"intent": string, "action": string}}, // use ONLY intents/actions from the provided lists
        "belief_state": {{ "<slot_name>": string }}    // USE ONLY the filled slots from {slot_list}; DO NOT include them when not filled
      }}, ...
    ]
  }}, ...
]

CONSTRAINTS (must obey):
1) Use only intents in {intent_list}, slots in {slot_list}, and actions in {action_list}. Do not invent or abbreviate any names. Strings must match exactly.
2) Generate only {num_samples} conversation objects for EACH intent present in {intent_list}. The output array length = {num_samples} * number_of_intents.
3) Each conversation can either focus on a single primary intent or change to another intent midway through. It can also include supporting or clarification turns that use other allowed intents — still only from the provided list.
4) Dialogue length MUST vary across samples (min 3 turns, max 12 turns). Ensure variation in:
   - number of turns
   - phrasing (use synonyms, change sentence structures)
   - slot-filling order (sometimes user provides all slots, occasionally partial and the agent asks clarifying Q's)
   - presence/absence of confirmations and negative cases (e.g., "no parking available" flow).
5) Uniqueness & diversity when {generated_samples} > 0:
   - Do not reproduce any previously-generated conversation exactly.
   - Ensure each produced sample differs from previous ones by at least one of: different slot values, different utterance phrasing (paraphrase), different dialogue length, or different turn ordering.
   - Use the dialogue_id suffix to ensure uniqueness: format <intent>_<counter>_<random8> where random8 is 8 hex chars.
   - Optionally, if provided, consider {previous_example_hashes} (an array of short hashes) to avoid collisions.
6) Strict formatting:
   - Output exactly one single-line JSON array (no newline characters anywhere).
   - No extra keys, no commentary strings, no trailing commas.
   - All dialogue_acts.intent and dialogue_acts.action must be non-empty strings; if no action at that turn, set action to "" (empty string).
7) System responses must be helpful and not only repeat the user's last utterance. 
8) Randomization requirement: Vary slot values across samples. Use different dates, numbers, names, times, and paraphrases. Avoid template-copying.
10) If any constraint cannot be satisfied, return ["ERROR: <clear reason>"].

{mix_it_up}

Now generate the examples following the rules above - output exactly one single-line JSON array and nothing else.
"""
# Make sure you include the intent and action in each dialogue act field. If there is no action to be taken on this turn, do not fill this slot.


FINETUNE_PROMPT = """<|start_header_id|>system<|end_header_id|>
You are a conversational agent with the following persona:
{description}

ALLOWED INTENTS:
{intent_list}

ALLOWED SLOTS (must match exactly):
{slot_list}

ALLOWED ACTIONS (with their required slots):
{action_list}

TASK:
Given the current conversation history, generate EXACTLY one JSON object that describes ONLY the next system turn. The output MUST be a single JSON object and nothing else.

REQUIRED JSON SCHEMA (top-level keys and order MUST be exactly):
    "system_response" : string
    "dialogue_acts"   : object with keys {{ "intent": string, "action": string}} — "action" may be "" if none
    "belief_state"    : object with ALL slots from {slot_list} as keys (ONLY include filled slots here)

STRICT FORMAT RULES:
1. Output must be ONLY the JSON object — no extra text, no explanations, no labels, no prefixes, no suffixes, no additional JSON objects.
2. Do not add or remove keys. Do not reorder top-level keys.
3. Use ONLY intents from {intent_list}, slots from {slot_list}, and actions from {action_list}. Do not invent or abbreviate any names. Strings must match exactly.
4. If the SYSTEM turn includes a slot reference AND an action, replace slot values in the "system_response" with the placeholder format "<slot_name>".
5. The "belief_state" object must contain ONLY allowed slots which are filled.
6. "system_response" must not repeat the user's last utterance verbatim. It should advance the conversation.
7. Wording should be natural, concise, and free of extraneous commentary.
8. You are ONLY to generate 1 JSON object as your response. Do not generate duplicate entries.

DIVERSITY RULES:
1. Vary phrasings used in your "system_response" compared to earlier turns in the same or previous conversations.
2. Avoid reusing the same wording or slot combinations already seen in prior outputs for the same intent.

EXAMPLES:
(keep examples out of final output; they are for guidance only)
Example 1:
CONV_HISTORY:
USER: I want to book a hotel room from August 12th to August 15th.
Dialogue State:
{{
    "system_response": "Got it. I'll reserve a room for you from August 12th to August 15th. Do you have a preferred bed type?",
    "dialogue_acts": {{"intent" : "book_room", "action" : "makeBooking"}},
    "belief_state": {{"dateFrom" : "August 12th", "dateTo" : "August 15th"}}
}}

Example 2:
CONV_HISTORY:
SYSTEM: How can I help you today?
USER: I'd like to cancel my hotel booking please.
Dialogue State:
{{
    "system_response": "Sure, I can cancel your booking. Could you provide your booking ID?",
    "dialogue_acts": {{"intent" : "cancel_booking", "action" : ""}},
    "belief_state": {{}}
}}

Example 3
CONV_HISTORY:
USER: My booking ID is 78910.
Dialogue State:
{{
    "system_response": "Thanks. I've cancelled your reservation with booking ID 78910. Is there anything else I can help you with?",
    "dialogue_acts": {{"intent" : "cancel_booking", "action" : "cancelBooking"}},
    "belief_state": {{"bookingID" : "78910"}}
}}

Example 4:
CONV_HISTORY:
USER: Do you have a suite available for this weekend?
Dialogue State:
{{
    "system_response": "Let me check. Could you tell me your exact check-in and check-out dates?",
    "dialogue_acts": {{"intent" : "book_room", "action" : ""}},
    "belief_state": {{}}
}}

Example 5:
CONV_HISTORY:
USER: I want to change my check-out date to July 22nd.
Dialogue State:
{{
    "system_response": "No problem, I'll update your check-out date to July 22nd. Is the check-in date staying the same?",
    "dialogue_acts": {{"intent" : "modify_booking", "action" : "updateBooking"}},
    "belief_state": {{"dateFrom" : "July 15th ", "dateTo" : "July 22nd", "bookingID" : "BK55667"}}
}}

<|start_header_id|>user<|end_header_id|>
Conversation history so far:
{conv_history}
<|start_header_id|>assistant<|end_header_id|>
Dialogue State:
"""

CONV_PROMPT = """
You are a customer agent whose job is to interact with a Digital Virtual Agent.
Engage with the virtual agent based on the following information about the Agent's capabilities:

{intent_list}

{slot_list} 

{action_slot_pair}

The intent you are to adhere to is {current_intent}

Here is the current conversation so far:
{conv_history}

This will be Conversation number {conv_number} you will be generating. Please keep this in mind when generating turns and try not to generate existing conversations.

Here are some guidelines for the conversation:
    - Engage in the same way a real human would. No overly long utterances, straight to the point (not always though).
    - Vary your speaking style: sometimes polite, sometimes casual, sometimes impatient, sometimes chatty.
    - Express slot values in diverse ways (e.g., "June 15th", "the 15th of June", "next Saturday", "from the 15th through the 20th").
    - Do not always start the conversation the same way. Sometimes open directly with the request, sometimes with small talk, sometimes with a clarifying question.
    - Occasionally act a bit unpredictable, like changing your mind mid-conversation, asking for clarification, or giving extra details the agent didn’t ask for.
    - Don’t repeat phrasing across conversations; make sure wording feels fresh.
    - Make up slot information where you need to.
    - Your response should just be your response to the agent's utterance in the JSON metadata block. Don't include any other verbose explanations and don't include markdown syntax anywhere.
    - Make up slot information where you need to.

Provide a structured JSON metadata block (and nothing else) that captures the following fields:
        {{
          "user_utterance": "...",        // your natural language response
          "predicted_system_response": "...",       // the expected system response
          "goal_completed": true/false,   // did you complete your intent
          "task_success": true/false,     // did the system succeed in helping
          "dialogue_acts": {{ "intent": "...", "action": "..."}} // predicted intent and action to take. 
          "belief_state": {{…}}, // current belief state of conversation - include only collected slots here, nothing else.
          "dialog_turn": <int>,           // current turn count
        }}

CONSTRAINTS for filling in the above (must obey):
1) Use only intents in {intent_list}, slots in {slot_list}, and actions in {action_slot_pair}. Do not invent or abbreviate any names. Strings must match exactly.
2) Do not include actions or intents in the belief state. Those belong in the dialogue acts section.
3) For the dialogue acts, if there is no action from the above list, leave as an empty string. If the conversation does not match a specified intent above, you may leave the field blank.
"""


EVALUATE_CHAT_PROMPT = """"
You are a customer agent evaluating a virtual agent's interaction with a customer. 
Give a critique of the bots performance across the conversation and suggest some improvements based on the bots existing structure:

{intent_list}

{slot_list}

The intent to be evaluated is {current_intent}

Here is the current conversation so far:
{conv_history}

Here are some guidelines for the critique:
For each system turn, generate a system response you think is valid for that turn.
    - Your response should just be your critque. Don't include any other verbose explanations and don't include markdown syntax anywhere.
    - Your response should be a critique of the bot's performance and suggest some improvements based on the bot's existing structure.
"""