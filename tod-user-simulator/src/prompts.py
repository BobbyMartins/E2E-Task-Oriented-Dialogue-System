from langchain.evaluation.agents.trajectory_eval_prompt import EVAL_CHAT_PROMPT

CONV_PROMPT = """
You are a customer agent whose job is to interact with a Digital Virtual Agent.
Engage with the virtual agent based on the following information about the Agent's capabilities:

{intent_list}

{slot_list}

The intent you are to adhere is {current_intent}

Here is the current conversation so far:
{conv_history}

Here are some guidelines for the conversation:
    - Engage in the same way a real human would. No overly long utterances, straight to the point (not always though).
    - Your response should just be your response to the agent's utterance. Don't include any other verbose explanations and don't include markdown syntax anywhere.
    - Make up slot information where you need to.
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
    - Your response should just be your critque. Don't include any other verbose explanations and don't include markdown syntax anywhere.
    - Your response should be a critique of the bot's performance and suggest some improvements based on the bot's existing structure.
"""