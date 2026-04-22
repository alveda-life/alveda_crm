"""
Role-based permission defaults for all CRM sections.
Stored in DB via RolePermission model; admin can override via API.
"""

SECTIONS = {
    'partners':             ['view', 'create', 'edit', 'delete'],
    'producers_onboarding': ['view', 'create', 'edit', 'delete'],
    'producers_support':    ['view', 'create', 'edit', 'delete'],
    'tasks':                ['view', 'create', 'edit', 'delete'],
    'reports':              ['view', 'create'],
    'analytics':            ['view'],
    'operators':            ['view'],
    'operator_activity':    ['view'],
}

_T = True
_F = False

ROLE_DEFAULTS = {
    'admin': {
        'partners':             {'view': _T, 'create': _T, 'edit': _T, 'delete': _T},
        'producers_onboarding': {'view': _T, 'create': _T, 'edit': _T, 'delete': _T},
        'producers_support':    {'view': _T, 'create': _T, 'edit': _T, 'delete': _T},
        'tasks':                {'view': _T, 'create': _T, 'edit': _T, 'delete': _T},
        'reports':              {'view': _T, 'create': _T},
        'analytics':            {'view': _T},
        'operators':            {'view': _T},
        'operator_activity':    {'view': _T},
    },
    'operator': {
        'partners':             {'view': _T, 'create': _F, 'edit': _F, 'delete': _F},
        'producers_onboarding': {'view': _F, 'create': _F, 'edit': _F, 'delete': _F},
        'producers_support':    {'view': _F, 'create': _F, 'edit': _F, 'delete': _F},
        'tasks':                {'view': _T, 'create': _T, 'edit': _T, 'delete': _F},
        'reports':              {'view': _T, 'create': _F},
        'analytics':            {'view': _F},
        'operators':            {'view': _F},
        'operator_activity':    {'view': _F},
    },
    'producer_onboarding': {
        'partners':             {'view': _F, 'create': _F, 'edit': _F, 'delete': _F},
        'producers_onboarding': {'view': _T, 'create': _T, 'edit': _T, 'delete': _F},
        'producers_support':    {'view': _F, 'create': _F, 'edit': _F, 'delete': _F},
        'tasks':                {'view': _T, 'create': _T, 'edit': _T, 'delete': _F},
        'reports':              {'view': _F, 'create': _F},
        'analytics':            {'view': _F},
        'operators':            {'view': _F},
        'operator_activity':    {'view': _F},
    },
    'producer_support': {
        'partners':             {'view': _F, 'create': _F, 'edit': _F, 'delete': _F},
        'producers_onboarding': {'view': _F, 'create': _F, 'edit': _F, 'delete': _F},
        'producers_support':    {'view': _T, 'create': _T, 'edit': _T, 'delete': _F},
        'tasks':                {'view': _T, 'create': _T, 'edit': _T, 'delete': _F},
        'reports':              {'view': _F, 'create': _F},
        'analytics':            {'view': _F},
        'operators':            {'view': _F},
        'operator_activity':    {'view': _F},
    },
    'producer_operator': {
        'partners':             {'view': _F, 'create': _F, 'edit': _F, 'delete': _F},
        'producers_onboarding': {'view': _T, 'create': _T, 'edit': _T, 'delete': _F},
        'producers_support':    {'view': _T, 'create': _T, 'edit': _T, 'delete': _F},
        'tasks':                {'view': _T, 'create': _T, 'edit': _T, 'delete': _F},
        'reports':              {'view': _T, 'create': _F},
        'analytics':            {'view': _F},
        'operators':            {'view': _F},
        'operator_activity':    {'view': _F},
    },
}


def get_role_defaults(role: str) -> dict:
    import copy
    return copy.deepcopy(ROLE_DEFAULTS.get(role, ROLE_DEFAULTS['operator']))
