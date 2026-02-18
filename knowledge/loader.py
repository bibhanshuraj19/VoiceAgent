import json
import logging

log = logging.getLogger("knowledge")

def load_knowledge(path: str = "knowledge/knowledge.json") -> str:
    try:
        with open(path) as f:
            data = json.load(f)
            log.info(f"Knowledge base loaded from {path}")
            return json.dumps(data)
    except FileNotFoundError:
        log.warning(f"Knowledge file not found at {path}. Continuing without it.")
        return "No additional knowledge provided."
    except json.JSONDecodeError as e:
        log.error(f"Knowledge file is not valid JSON: {e}")
        return "No additional knowledge provided."