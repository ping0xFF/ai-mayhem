from litellm import completion
import os
import json
from datetime import datetime
import logging
from dotenv import load_dotenv
from litellm.exceptions import AuthenticationError, NotFoundError, RateLimitError

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY not found in environment variables")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def calculate_cost(input_tokens, output_tokens, model):
    # Cost rates per 1K tokens (you may need to update these based on current pricing)
    COST_PER_1K_INPUT = 0.00025  # $0.00025 per 1K input tokens for Claude 3 Haiku
    COST_PER_1K_OUTPUT = 0.00075  # $0.00075 per 1K output tokens for Claude 3 Haiku
    
    input_cost = (input_tokens / 1000) * COST_PER_1K_INPUT
    output_cost = (output_tokens / 1000) * COST_PER_1K_OUTPUT
    return input_cost + output_cost

def log_request(prompt, response, model, input_tokens, output_tokens):
    try:
        estimated_cost = calculate_cost(input_tokens, output_tokens, model)
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_cost": estimated_cost,
            "prompt": prompt,
            "response": response
        }
        
        os.makedirs("logs", exist_ok=True)  # Ensure logs directory exists
        with open("logs/requests.json", "a") as f:
            f.write(json.dumps(log_entry) + "\n")
            
        logger.info(f"Request logged. Cost: ${estimated_cost:.4f}")
    except Exception as e:
        logger.error(f"Failed to log request: {e}")

def test_completion():
    try:
        prompt = "Hello from my 24/7 agent project"
        logger.info(f"Sending request with prompt: {prompt}")
        
        response = completion(
            model="claude-3-haiku-20240307",
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Log the request and response
        log_request(
            prompt=prompt,
            response=response.choices[0].message.content,
            model=response.model,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens
        )
        
        # Calculate and display cost
        cost = calculate_cost(
            response.usage.prompt_tokens,
            response.usage.completion_tokens,
            response.model
        )
        
        print("Response:", response.choices[0].message.content)
        print(f"Cost: ${cost:.4f}")
        
    except AuthenticationError as e:
        logger.error(f"Authentication error: {e}")
        print("Please check your API key")
    except NotFoundError as e:
        logger.error(f"Model not found error: {e}")
        print("Please check the model name")
    except RateLimitError as e:
        logger.error(f"Rate limit exceeded: {e}")
        print("Please try again later")
    except Exception as e:
        logger.error(f"Unexpected error during completion: {e}")
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    test_completion()