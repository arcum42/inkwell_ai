"""Schema registry for structured (JSON) responses.

Provides a simple in-memory registry of named JSON Schemas and metadata,
including provider allowlists. Tools and features can register schemas
and query by id.
"""

from typing import Dict, Optional, List, Any


class SchemaRegistry:
    def __init__(self):
        # schema_id -> { 'schema': dict, 'description': str, 'version': str, 'providers': Optional[List[str]] }
        self._schemas: Dict[str, Dict[str, Any]] = {}

    def register_schema(
        self,
        schema_id: str,
        schema: Dict[str, Any],
        *,
        description: Optional[str] = None,
        version: Optional[str] = None,
        providers: Optional[List[str]] = None,
    ) -> None:
        """Register or update a schema under the given id.
        providers: list of provider class names allowed to use this schema; None means all.
        """
        self._schemas[schema_id] = {
            'schema': schema,
            'description': description or '',
            'version': version or '1.0.0',
            'providers': providers,  # e.g., ['LMStudioNativeProvider']
        }

    def get_schema(self, schema_id: str) -> Optional[Dict[str, Any]]:
        entry = self._schemas.get(schema_id)
        return entry['schema'] if entry else None

    def get_entry(self, schema_id: str) -> Optional[Dict[str, Any]]:
        return self._schemas.get(schema_id)

    def list_schemas(self, allowed_provider: Optional[str] = None) -> List[Dict[str, Any]]:
        out = []
        for sid, entry in self._schemas.items():
            providers = entry.get('providers')
            if allowed_provider is None or providers is None or allowed_provider in providers:
                out.append({'id': sid, **entry})
        return out


_registry = SchemaRegistry()


def register_schema(schema_id: str, schema: Dict[str, Any], *, description: Optional[str] = None, version: Optional[str] = None, providers: Optional[List[str]] = None) -> None:
    _registry.register_schema(schema_id, schema, description=description, version=version, providers=providers)


def get_schema(schema_id: str) -> Optional[Dict[str, Any]]:
    return _registry.get_schema(schema_id)


def get_entry(schema_id: str) -> Optional[Dict[str, Any]]:
    return _registry.get_entry(schema_id)


def list_schemas(allowed_provider: Optional[str] = None) -> List[Dict[str, Any]]:
    return _registry.list_schemas(allowed_provider)


# Seed starter schemas
register_schema(
    'basic_answer',
    {
        'type': 'object',
        'properties': {
            'answer': {'type': 'string'},
            'notes': {'type': 'string'},
        },
        'required': ['answer'],
        'additionalProperties': False,
    },
    description='Basic answer with optional notes',
    providers=['LMStudioNativeProvider'],
)

register_schema(
    'diff_patch',
    {
        'type': 'object',
        'properties': {
            'summary': {'type': 'string'},
            'edits': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'path': {'type': 'string'},
                        'before': {'type': 'string'},
                        'after': {'type': 'string'},
                        'warnings': {'type': 'array', 'items': {'type': 'string'}},
                    },
                    'required': ['path', 'after'],
                    'additionalProperties': False,
                },
            },
            'warnings': {'type': 'array', 'items': {'type': 'string'}},
        },
        'required': ['edits'],
        'additionalProperties': False,
    },
    description='Structured diffs/updates',
    providers=['LMStudioNativeProvider'],
)

register_schema(
    'tool_result',
    {
        'type': 'object',
        'properties': {
            'request': {'type': 'string'},
            'result': {},
            'citations': {'type': 'array', 'items': {'type': 'string'}},
        },
        'required': ['result'],
        'additionalProperties': True,
    },
    description='Generic tool output with citations',
    providers=['LMStudioNativeProvider'],
)

register_schema(
    'chat_split',
    {
        'type': 'object',
        'properties': {
            'analysis': {'type': 'string'},
            'answer': {'type': 'string'},
            'actions': {'type': 'array', 'items': {'type': 'string'}},
        },
        'required': ['answer'],
        'additionalProperties': False,
    },
    description='Separate discussion from final answer',
    providers=['LMStudioNativeProvider'],
)
