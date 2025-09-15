from functools import wraps
from langchain.prompts import PromptTemplate
from langchain_aws import ChatBedrock
import time

from nlu_api_framework import NluAPIFramework
from prompts import CONV_PROMPT
from safe.conf import start_botflow_session, send_botflow_turn_event


def retry(max_retries=3, retry_delay=5):
    """Decorator to retry a function or staticmethod if it raises an exception.

    :param max_retries: The maximum number of attempts to retry.
    :param retry_delay: The delay in seconds between retries.
    :return: A decorator that wraps the function or classmethod.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    print(f"Retrying {func.__name__} due to exception: {e}")
                    time.sleep(retry_delay)
            else:
                raise Exception(f"Maximum retries ({max_retries}) exceeded for {func.__name__}")

        return wrapper

    return decorator


@retry(max_retries=3, retry_delay=5)
def get_claude_response(
    prompt_string,
    prompt_params,
    model_id="anthropic.claude-3-haiku-20240307-v1:0",
    model_kwargs={
        "max_tokens": 200,
        "temperature": 1.0,
        # "top_k": 1,
        "top_p": 1,
        "stop_sequences": ['User:', '</assistant>'],
    },
):
    model = ChatBedrock(
        region_name="us-east-1",
        model_id=model_id,
        model_kwargs=model_kwargs
    )
    prompt = PromptTemplate.from_template(prompt_string)
    chain = prompt | model  # | SimpleJsonOutputParser() # LCEL
    return chain.invoke(prompt_params)


def main():
    # Initialize NLU API
    flow_id = 'a260b009-1fe7-4785-921d-86b44f74cf63'
    org_id = '3893d439-310d-47fe-a218-93823ad044a5'
    base_url = 'https://language-understanding-service.prv-use1-ai.dev-pure.cloud'
    nlu_api = NluAPIFramework(org_id, base_url)
    version_deets = nlu_api.show_domain_version_details('11e87964-c188-4626-98f1-462a472d07af', 'b586e69c-50c0-49ad-82a0-9719a10aa612')[1]

    # Process intent and slot lists
    intent_list = {}
    slot_list = {}
    for intent in version_deets['intents']:
        intent_list[intent['name']] = intent['description']
        for slot in intent['entityNameReferences']:
            if slot in slot_list:
                slot_list[slot].append(intent['name'])
            else:
                slot_list[slot] = [intent['name']]

    print(intent_list, slot_list)

    # Start conversation
    end_convo = False
    current_intent = list(intent_list.keys())[0]
    conv_history = []

    session_id, bot_response, expected_action, previous_turn_id = start_botflow_session(flow_id)
    conv_history.append(bot_response)

    while not end_convo:
        current_intent = list(intent_list.keys())[0]

        example = get_claude_response(prompt_string=CONV_PROMPT,
                                    prompt_params={
                                        'intent_list': str(intent_list),
                                        'slot_list': str(slot_list),
                                        'current_intent': current_intent,
                                        "conv_history": '\n'.join(conv_history)
                                    },
                                    model_id='anthropic.claude-3-5-sonnet-20240620-v1:0')

        print(example.content)

        response = send_botflow_turn_event(session_id, 'USER_INPUT', text=example.content, previous_turn_id=previous_turn_id)

        try:
            agent_response, expected_action, previous_turn_id = response['prompts']['textPrompts']['segments'][0]['text'], response['nextActionType'], response['id']
        except KeyError:
            print(response)
            end_convo = True

        print(response['prompts']['textPrompts']['segments'][0]['text'])

        conv_history.append(f"USER: {example.content}")
        conv_history.append(f"AGENT: {agent_response}")

        # print(conv_history)

        if expected_action == 'NoOp':
            end_convo = True


if __name__ == "__main__":
    main()