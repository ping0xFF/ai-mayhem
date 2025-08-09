from litellm import completion
import os
import json
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def log_request(prompt, response, model, input_tokens, output_tokens, cost):
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost": cost,
        "prompt": prompt,
        "response": response
    }
    
    with open("logs/requests.json", "a") as f:
        f.write(json.dumps(log_entry) + "\n")

def test_completion():
    try:
        prompt = "Hello from my 24/7 agent project"
        response = completion(
            model="anthropic/claude-3-haiku",
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Log the request and response
        log_request(
            prompt=prompt,
            response=response.choices[0].message.content,
            model=response.model,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            cost=response.usage.total_cost
        )
        
        print("Response:", response.choices[0].message.content)
        print(f"Cost: ${response.usage.total_cost:.4f}")
        
    except Exception as e:
        logger.error(f"Error during completion: {e}")
        raise

if __name__ == "__main__":
    test_completion()
