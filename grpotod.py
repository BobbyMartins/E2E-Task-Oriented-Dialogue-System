from unsloth import FastLanguageModel
import sys
import os
from peft import PeftModel
# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

import copy
import time
import json
import ast
from prompts import FINETUNE_PROMPT
import torch


def safe_parse_json_or_python(s):
    """Try parsing as JSON first, then as Python literal."""
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        try:
            return ast.literal_eval(s)
        except Exception as err:
            raise Exception


def extract_llm_response(text: str) -> str:
    answer = text.split('\nDialogue State:\n')[-1]
    return answer.strip()

class GRPOTODAgent():
    def __init__(self, model_path="./././init_ft_000-merged",
                 max_seq_length=4096,
                 lora_rank=32,
                 fast_inference=True,
                 gpu_memory_utilization=0.70,
                 description="A helpful hotel booking assistant",
                 lora_on_top=False,
                 intent_list=None,
                 slot_list=None,
                 action_list=None,
                 name="GRPOTOD"):

        if action_list is None:
            action_list = action_slot_pair = {
                "makeBooking": ("dateFrom", "dateTo"),
                "lookUpBooking": ("bookingID"),
                "cancellation": ("bookingID")
            }
        if intent_list is None:
            intent_list = {
                "book_room": "The user wants to book a room in the hotel",
                "cancel_booking": "The user wants to cancel an existing booking",
                "general_enquiries": "The user wants to ask general questions about the hotel",
                "chit_chat": "Queries outside of the other intents specified. Apart from greetings and hellos, the response for this one should be 'Sorry, I can only help you with hotel queries.'"
            }

        if slot_list is None:
            slot_list = {
                "dateFrom", ('book_room'),
                "dateTo", ('book_to'),
                "bookingID", ("cancel_booking")
            }

        self.max_seq_length = max_seq_length
        self.lora_rank = lora_rank
        self.description = description
        self.intent_list = intent_list
        self.slot_list = slot_list
        self.action_list = action_list

        if not lora_on_top:
            # Load model using unsloth
            self.model, self.tokenizer = FastLanguageModel.from_pretrained(
                model_name=model_path,
                max_seq_length=max_seq_length,
                fast_inference=fast_inference,
                max_lora_rank=lora_rank,
                gpu_memory_utilization=gpu_memory_utilization
            )
            
        # Apply LoRA if lora adapter provided
    
        else:
            print("LOADING BASE MODEL FIRST")
            self.model, self.tokenizer = FastLanguageModel.from_pretrained(
                model_name = "unsloth/Meta-Llama-3.1-8B",
                max_seq_length = max_seq_length,
                dtype = None,
                # load_in_4bit = True, # False for LoRA 16bit
                fast_inference = True, # Enable vLLM fast inference
                max_lora_rank = lora_rank,
                gpu_memory_utilization = 0.70
            )
        
            self.model = PeftModel.from_pretrained(self.model, model_path)
        
        self.model.eval()
        self.device = next(self.model.parameters()).device
        
        self.prompt_template = FINETUNE_PROMPT
        
        self.init_session()
    
    def init_session(self):
        self.conversation_history = []
        self.belief_state = {slot: "" for slot in self.slot_list}
    
    def response(self, user_input):
        """Generate agent response given user input."""
        self.conversation_history.append(f"USER: {user_input}")
        
        # Prepare conversation history
        conv_history = "\n".join(self.conversation_history[-10:])
        
        # Format prompt
        prompt = self.prompt_template.format(
            description=str(self.description),
            intent_list=str(self.intent_list),
            slot_list=str(self.slot_list),
            action_list=str(self.action_list),
            conv_history=str(conv_history)
        )
        
        # Tokenize
        inputs = self.tokenizer([prompt], return_tensors="pt").to("cuda")
        
        # Generate
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=512,
                use_cache = True,
                do_sample=False,
                pad_token_id=self.tokenizer.eos_token_id,
                eos_token_id=self.tokenizer.eos_token_id
            )

        # Decode response
        full_response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        try:
            raw_response = extract_llm_response(full_response)
            # Parse JSON response
            dialogue_state = safe_parse_json_or_python(raw_response)
            system_response = dialogue_state.get("system_response", "")
            
            # Update belief state
            if "belief_state" in dialogue_state:
                self.belief_state.update(dialogue_state["belief_state"])
            
            self.conversation_history.append(f"SYSTEM: {system_response}")
            return dialogue_state, system_response
        except Exception as err:
            print(raw_response)
            print(err)
            # Fallback if JSON parsing fails
            fallback_response = "I'm sorry, could you please repeat that?"
            self.conversation_history.append(f"SYSTEM: {fallback_response}")
            return fallback_response


if __name__ == '__main__':
    agent = GRPOTODAgent()
    
    user_input = "What is life mehn"
    response = agent.response(user_input)
    print(f"User: {user_input}")
    print(f"Agent: {response}")
    print(f"Belief State: {agent.belief_state}")

