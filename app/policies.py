"""Policy truth source for roles and their forbidden intents."""

ROLE_POLICIES = {
    'client': {
        'forbidden_intents': [
            'access_other_users_data',
            'exfiltrate_sensitive_data',
        ]
    },
    'lawyer': {
        'forbidden_intents': [
            'access_other_users_data',
            'exfiltrate_sensitive_data',
            'perform_unapproved_surveillance',
        ]
    },
    'admin': {
        'forbidden_intents': [
            'exfiltrate_sensitive_data',
        ]
    }
}
