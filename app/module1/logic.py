"""Authorization logic for Module 1 (Identity Guard)."""
from app.policies import ROLE_POLICIES

# Map forbidden intent names to example keywords/phrases to detect in prompts
FORBIDDEN_INTENT_KEYWORDS = {
    'access_other_users_data': [
        'access other users', 'other users data', 'user data of', 'get user data', 'access account of', 'steal user data'
    ],
    'exfiltrate_sensitive_data': [
        'ssn', 'social security', 'credit card', 'creditcard', 'cvv', 'password', 'secret', 'private key', 'private data'
    ],
    'perform_unapproved_surveillance': [
        'surveillance', 'track', 'spy on', 'monitor user', 'track user', 'monitoring user'
    ],
}


def is_authorized(user_role, user_prompt):
    """Return True if the role is allowed to make the request in `user_prompt`.

    The function checks the role's forbidden intents and looks for
    keyword occurrences in the prompt. If any forbidden keyword is found,
    the function returns False (unauthorized).
    """
    if not user_role or not user_prompt:
        return False

    role = str(user_role).lower()
    prompt = str(user_prompt).lower()

    policy = ROLE_POLICIES.get(role)
    if not policy:
        # Unknown role -> deny by default
        return False

    for intent in policy.get('forbidden_intents', []):
        keywords = FORBIDDEN_INTENT_KEYWORDS.get(intent, [])
        for kw in keywords:
            if kw in prompt:
                return False

    return True


def find_forbidden_intents(user_role, user_prompt):
    """Return a list of forbidden intent names that match the prompt for the role."""
    if not user_role or not user_prompt:
        return []

    role = str(user_role).lower()
    prompt = str(user_prompt).lower()

    policy = ROLE_POLICIES.get(role)
    if not policy:
        return []

    matches = []
    for intent in policy.get('forbidden_intents', []):
        keywords = FORBIDDEN_INTENT_KEYWORDS.get(intent, [])
        for kw in keywords:
            if kw in prompt:
                matches.append(intent)
                break
    return matches
