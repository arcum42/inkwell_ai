# LLM Tools System Design

## Current Architecture

### Overview
Inkwell AI implements an LLM tool system that allows the AI assistant to interact with external resources and perform actions beyond text generation. The current implementation uses a string-pattern-based approach where tools are invoked via special markup in LLM responses.

### Current Tools

#### 1. **Web Reader** (`WEB_READ`)
**Purpose:** Fetch and read content from web pages

**Implementation:** `core/tools.py` - `WebReader` class

**Usage Pattern:** `:::TOOL:WEB_READ:https://url...:::`

**Features:**
- HTTP GET with custom User-Agent
- BeautifulSoup parsing to extract clean text
- Removes script/style elements
- Whitespace cleanup
- Content limited to 10,000 characters
- 10-second timeout

**Limitations:**
- No JavaScript rendering
- Fixed character limit may truncate long articles
- Limited error handling
- No caching of frequently accessed URLs

#### 2. **Web Searcher** (`SEARCH`)
**Purpose:** Search the web using DuckDuckGo

**Implementation:** `core/tools.py` - `WebSearcher` class

**Usage Pattern:** `:::TOOL:SEARCH:query...:::`

**Features:**
- Returns top 5 results
- Formatted with title, URL, and description
- Dependency-aware (gracefully handles missing library)

**Limitations:**
- Fixed result count (5)
- No filtering options (date, domain, etc.)
- Requires `duckduckgo-search` library
- No result caching

#### 3. **Wikipedia Tool** (`WIKI`)
**Purpose:** Search and retrieve Wikipedia article summaries

**Implementation:** `core/tools.py` - `WikiTool` class

**Usage Pattern:** `:::TOOL:WIKI:query...:::`

**Features:**
- Uses Wikipedia REST API
- Returns formatted summary with link
- Proper User-Agent identification

**Limitations:**
- Only returns summary (not full article)
- English Wikipedia only
- No disambiguation handling
- First search result only

#### 4. **Image Searcher** (`IMAGE`)
**Purpose:** Search for images using DuckDuckGo

**Implementation:** `core/tools.py` - `ImageSearcher` class

**Usage Pattern:** `:::TOOL:IMAGE:query...:::`

**Features:**
- Returns up to 10 image results
- Opens dialog for user selection
- Can save selected images to project
- Returns structured data (URLs, titles, etc.)

**Limitations:**
- Fixed result count (10)
- No filtering (size, type, license)
- Requires `duckduckgo-search` library
- No local image search

### Invocation Mechanism

**Tool Execution Flow:**
1. User sends message to chat
2. `ChatWorker` adds tool capability instructions to message
3. LLM generates response with `:::TOOL:NAME:query:::` pattern
4. `on_chat_response()` in `main_window.py` parses tool pattern
5. `ToolWorker` thread executes the tool
6. Result fed back to LLM via `continue_chat_with_tool_result()`
7. LLM generates final response to user

**Key Files:**
- `core/tools.py` - Tool implementations
- `gui/workers.py` - `ToolWorker` and `ChatWorker` classes
- `gui/main_window.py` - Tool invocation handling

**Pattern Recognition:**
```python
tool_pattern = r":::TOOL:(.*?):(.*?):::"
# Example: :::TOOL:SEARCH:python tutorials:::
```

---

## Proposed Improvements

### 0. Context Window Optimization

**Motivation:** Large files and complex edits can exceed LLM context windows. The current `:::UPDATE:::` system requires the LLM to generate entire file contents, which is inefficient and error-prone for large files.

**Problems with Current Approach:**
- LLM must fit entire file in context to edit it
- Token costs increase linearly with file size
- Risk of truncation or incomplete edits
- Can't easily make systematic changes (e.g., "rename X to Y everywhere")
- No way to edit multiple files efficiently

**Solution: Batch Search and Replace Tools**

Instead of having the LLM rewrite entire files, provide tools for targeted modifications:
- Single-file search/replace for specific changes
- Multi-file batch operations for project-wide updates
- Regex support for complex patterns
- Preview/confirmation workflow for safety
- No need to load full file content into LLM context

**Impact:**
- Reduces context window usage by ~90% for large file edits
- Enables editing files larger than context window
- Makes project-wide refactoring feasible
- Lower token costs
- Faster operations

See **Batch Search and Replace Tool** section below for detailed implementation.

### 1. Plugin-Based Tool Architecture

**Motivation:** Current system is rigid with hardcoded tool names and implementations. Adding new tools requires modifying multiple files.

**Proposal:** Implement a base `Tool` class with a registry system:

```python
# core/tool_base.py
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

class Tool(ABC):
    """Base class for LLM tools."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool identifier."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description for LLM context."""
        pass
    
    @property
    def requires_libraries(self) -> list[str]:
        """Optional dependencies."""
        return []
    
    @abstractmethod
    def execute(self, query: str) -> tuple[str, Optional[Any]]:
        """Execute tool and return (result_text, extra_data)."""
        pass
    
    def is_available(self) -> bool:
        """Check if tool can be used (dependencies installed, etc.)."""
        return True
    
    def get_usage_pattern(self) -> str:
        """Return the invocation pattern for LLM."""
        return f":::TOOL:{self.name}:query...:::"

class ToolRegistry:
    """Central registry for all available tools."""
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
    
    def register(self, tool: Tool):
        """Register a tool."""
        self._tools[tool.name] = tool
    
    def unregister(self, name: str):
        """Remove a tool from registry."""
        if name in self._tools:
            del self._tools[name]
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """Get tool by name."""
        return self._tools.get(name)
    
    def get_available_tools(self) -> list[Tool]:
        """Get list of available (usable) tools."""
        return [t for t in self._tools.values() if t.is_available()]
    
    def get_tool_instructions(self) -> str:
        """Generate tool instructions for LLM context."""
        tools = self.get_available_tools()
        if not tools:
            return ""
        
        lines = ["You have access to the following tools:"]
        for i, tool in enumerate(tools, 1):
            lines.append(f"{i}. {tool.description}")
            lines.append(f"   Usage: {tool.get_usage_pattern()}")
        return "\n".join(lines)

# Global registry instance
_registry = ToolRegistry()

def get_registry() -> ToolRegistry:
    return _registry
```

**Benefits:**
- Easy to add/remove tools without modifying core logic
- Tools can declare their dependencies
- Self-documenting (description in tool class)
- Can disable tools at runtime
- Facilitates testing individual tools

### 2. Project-Specific Tool Configuration

**Motivation:** Not all projects need all tools. Some tools (like imageboard APIs) are only useful for specific projects.

**Proposal:** Project-level tool configuration:

```python
# .inkwell/config.json
{
    "enabled_tools": [
        "WEB_READ",
        "SEARCH",
        "WIKI",
        "PROJECT_SEARCH",
        "DERPIBOORU"
    ],
    "tool_settings": {
        "DERPIBOORU": {
            "api_key": "...",
            "default_filter": "safe"
        },
        "SEARCH": {
            "max_results": 10
        }
    }
}
```

**Implementation:**
- Store configuration in project directory
- Load on project open
- UI in Settings dialog to enable/disable tools
- Only pass enabled tools' instructions to LLM
- Reduces token usage for unused tools

### 3. Enhanced Existing Tools

#### Web Reader Improvements:
- **JavaScript rendering** using `playwright` or `selenium`
- **Configurable length limits** per project
- **Caching** with TTL to avoid repeated fetches
- **PDF support** using `PyPDF2` or `pdfplumber`
- **Content extraction modes** (article vs full page)

#### Search Improvements:
- **Configurable result counts**
- **Date filtering** (past day/week/month/year)
- **Domain filtering** (site:example.com)
- **Safe search toggle**
- **Alternative search engines** (SearX, custom)

#### Wikipedia Improvements:
- **Full article text** option
- **Multi-language support**
- **Disambiguation page handling**
- **Section extraction** (get specific section)
- **Related articles** suggestions

#### Image Search Improvements:
- **Size filtering** (small/medium/large/wallpaper)
- **Type filtering** (photo/clipart/line drawing)
- **License filtering** (creative commons, etc.)
- **Color filtering**
- **Local project image search**

### 4. New Tool Ideas

#### **Project File Search Tool**
```python
class ProjectSearchTool(Tool):
    name = "PROJECT_SEARCH"
    description = "Search project files: :::TOOL:PROJECT_SEARCH:query:::"
    
    def execute(self, query: str):
        # Use RAG engine or grep-like search
        # Return relevant file excerpts with paths
        pass
```

**Use Cases:**
- "Find all character descriptions"
- "Search for mentions of magic system"
- "Find TODO comments"

#### **Batch Search and Replace Tool**
```python
class BatchReplaceToolSingle(Tool):
    name = "BATCH_REPLACE"
    description = "Search and replace in a file: :::TOOL:BATCH_REPLACE:path|search_pattern|replacement|regex:::"
    
    def execute(self, query: str):
        # Parse: path|search|replace|is_regex
        # Apply replacements without loading full file to LLM context
        # Return count of replacements made
        # Show preview/confirmation dialog to user
        pass
```

```python
class BatchReplaceToolMulti(Tool):
    name = "BATCH_REPLACE_MULTI"
    description = "Search and replace across multiple files: :::TOOL:BATCH_REPLACE_MULTI:pattern|search|replace|regex:::"
    
    def execute(self, query: str):
        # Parse: file_pattern|search|replace|is_regex
        # Find matching files (glob pattern)
        # Apply replacements to all matches
        # Return summary of files modified and replacement count
        pass
```

**Benefits:**
- **Context window efficiency:** LLM doesn't need entire file content to make systematic changes
- **Precise operations:** Regex support for complex patterns
- **Multi-file changes:** Update function names, variable names across entire project
- **Performance:** Faster than loading, modifying, and saving large files
- **Undo support:** Can track batch operations for undo/redo

**Use Cases:**
- Rename functions/classes across entire codebase
- Update old API calls to new syntax
- Fix consistent typos or formatting issues
- Replace deprecated imports
- Update character names across multiple story files
- Change magic system terminology project-wide

**Safety Features:**
- **Preview mode:** Show what would change before applying
- **Dry-run option:** Report matches without modifying
- **File backup:** Auto-backup before batch operations
- **Confirmation dialog:** User must approve batch changes
- **Match limiting:** Prevent accidental mass-changes
- **Exclude patterns:** Skip certain files (e.g., `.git/`, `node_modules/`)

**Advanced Features:**
```python
class SmartReplaceTool(Tool):
    """Context-aware replacements."""
    name = "SMART_REPLACE"
    
    def execute(self, query: str):
        # Parse: path|old_text|new_text|context_lines
        # Only replace when surrounding context matches
        # Useful for replacing similar text in different contexts
        pass
```

**Example Usage:**

*Single file:*
```
LLM: I'll update the character name in Chapter1.md
:::TOOL:BATCH_REPLACE:Chapters/Chapter1.md|Johnathan|Jonathan|false:::
```

*Multiple files with regex:*
```
LLM: I'll fix all old-style function calls
:::TOOL:BATCH_REPLACE_MULTI:*.py|oldFunc\((.*?)\)|newFunc($1)|true:::
```

*Context-aware:*
```
LLM: I'll only replace "light" when referring to the magic system, not lighting
:::TOOL:SMART_REPLACE:worldbuilding.md|light|luminescence|magic,spell,power:::
```

**Implementation Notes:**
- Use `re.sub()` for regex replacements
- Track modifications for RAG re-indexing
- Emit signals to update open editor tabs
- Log all batch operations for debugging
- Support case-sensitive/insensitive modes
- Provide word-boundary matching option

#### **Derpibooru/Imageboard Tool**
```python
class DerpibooruTool(Tool):
    name = "DERPIBOORU"
    description = "Search Derpibooru images: :::TOOL:DERPIBOORU:query:::"
    
    def execute(self, query: str):
        # Use Derpibooru API
        # Return images with tags, scores, sources
        # Filter by rating (safe/questionable/explicit)
        pass
```

**Features:**
- Tag-based search
- Score/favorite filtering
- Rating control
- Artist filtering
- Download with metadata preservation

**Generalization:**
```python
class ImageboardTool(Tool):
    """Generic imageboard support."""
    
    SUPPORTED_BOARDS = {
        'derpibooru': 'https://derpibooru.org/api/',
        'danbooru': 'https://danbooru.donmai.us/api/',
        'gelbooru': 'https://gelbooru.com/api/',
    }
    
    def execute(self, query: str):
        # Parse board:query format
        # Route to appropriate API
        pass
```

#### **Code Execution Tool**
```python
class CodeExecutionTool(Tool):
    name = "PYTHON_EXEC"
    description = "Execute Python code: :::TOOL:PYTHON_EXEC:code:::"
    
    def execute(self, query: str):
        # Sandboxed execution
        # Capture stdout/stderr
        # Timeout protection
        pass
```

**Safety Considerations:**
- Sandboxing required (Docker, RestrictedPython, etc.)
- Timeout limits
- Resource limits
- User confirmation for dangerous operations

#### **Git Operations Tool**
```python
class GitTool(Tool):
    name = "GIT"
    description = "Git operations: :::TOOL:GIT:command:::"
    
    def execute(self, query: str):
        # Run git commands
        # Parse: "status", "log", "diff", etc.
        # Read-only by default
        pass
```

**Use Cases:**
- Check file history
- View recent commits
- See uncommitted changes
- Blame/annotate files

#### **Natural Language Date/Time Tool**
```python
class DateTimeTool(Tool):
    name = "DATETIME"
    description = "Get current date/time: :::TOOL:DATETIME:format:::"
    
    def execute(self, query: str):
        # Return formatted date/time
        # Support relative queries: "tomorrow", "next week"
        pass
```

#### **Calculation/Math Tool**
```python
class CalculatorTool(Tool):
    name = "CALC"
    description = "Evaluate math expressions: :::TOOL:CALC:expression:::"
    
    def execute(self, query: str):
        # Use sympy or eval (carefully!)
        # Support basic math, units, etc.
        pass
```

#### **Dictionary/Thesaurus Tool**
```python
class DictionaryTool(Tool):
    name = "DEFINE"
    description = "Get word definitions: :::TOOL:DEFINE:word:::"
    
    def execute(self, query: str):
        # Use WordNet, Dictionary API, etc.
        # Return definitions, synonyms, antonyms
        pass
```

#### **Translation Tool**
```python
class TranslationTool(Tool):
    name = "TRANSLATE"
    description = "Translate text: :::TOOL:TRANSLATE:from_lang|to_lang|text:::"
    
    def execute(self, query: str):
        # Use Google Translate API or LibreTranslate
        pass
```

#### **Weather Tool**
```python
class WeatherTool(Tool):
    name = "WEATHER"
    description = "Get weather info: :::TOOL:WEATHER:location:::"
    
    def execute(self, query: str):
        # Use OpenWeatherMap, wttr.in, etc.
        pass
```

### 5. Tool Composition/Chaining

**Concept:** Allow LLM to chain tools automatically:

```
:::TOOL:SEARCH:best python tutorial:::
[Results shown]
:::TOOL:WEB_READ:https://top-result-url:::
[Content shown]
```

**Implementation:**
- Track tool call depth to prevent infinite loops
- Allow LLM to request multiple tools in sequence
- Automatically feed results back

**Alternative:** Tool macros:
```python
class MacroTool(Tool):
    """Tool that executes multiple tools."""
    
    def __init__(self, name: str, steps: list[tuple[str, str]]):
        self._name = name
        self._steps = steps  # [(tool_name, query_template), ...]
    
    def execute(self, query: str):
        results = []
        for tool_name, query_template in self._steps:
            # Execute each tool
            # Use previous results in query template
            pass
```

Example macro: `SEARCH_AND_READ` - searches, then reads top result

### 6. Tool Result Formatting

**Current Issue:** Tool results fed back as plain text, which can be verbose.

**Improvements:**
- **Structured data:** Return JSON for structured results
- **Summarization:** Automatically summarize long tool outputs
- **Relevance filtering:** Only return relevant parts based on original query
- **Token-aware truncation:** Smart truncation that preserves key information

```python
class ToolResult:
    """Structured tool result."""
    
    def __init__(
        self,
        success: bool,
        data: Any,
        summary: str,
        full_text: str,
        metadata: dict
    ):
        self.success = success
        self.data = data
        self.summary = summary  # Brief for LLM
        self.full_text = full_text  # Full result if needed
        self.metadata = metadata  # Extra info (URL, timestamp, etc.)
    
    def to_llm_context(self, mode: str = "summary") -> str:
        """Format for LLM consumption."""
        if mode == "summary":
            return self.summary
        elif mode == "full":
            return self.full_text
        else:
            return self.data
```

### 7. Tool Access Control

**Motivation:** Some tools modify state or access sensitive data.

**Proposal:** Permission levels:
- **READ_ONLY:** Can query but not modify (search, read, etc.)
- **PROJECT_WRITE:** Can modify project files
- **SYSTEM_WRITE:** Can modify system (dangerous!)
- **NETWORK:** Can access network
- **USER_CONFIRMATION:** Requires user approval

```python
class Tool(ABC):
    @property
    def permissions(self) -> set[str]:
        return {"READ_ONLY"}

# In settings:
tool_permissions = {
    "WEB_READ": {"NETWORK"},
    "SEARCH": {"NETWORK"},
    "DERPIBOORU": {"NETWORK", "PROJECT_WRITE"},  # Can save images
    "GIT": {"SYSTEM_WRITE", "USER_CONFIRMATION"},
}
```

**UI:**
- Show permission requirements when enabling tools
- Prompt user before first use of privileged tool
- Log all tool executions

### 8. Tool Performance Monitoring

**Motivation:** Track tool usage and performance for debugging and optimization.

```python
class ToolMetrics:
    """Track tool usage statistics."""
    
    def __init__(self):
        self.calls = {}  # tool_name -> count
        self.errors = {}  # tool_name -> error_count
        self.latency = {}  # tool_name -> avg_ms
        self.last_used = {}  # tool_name -> timestamp
    
    def record_call(self, tool_name: str, latency_ms: float, success: bool):
        pass
    
    def get_report(self) -> str:
        """Generate usage report."""
        pass
```

**UI Integration:**
- Settings dialog shows tool usage stats
- Identify slow/failing tools
- Help optimize tool selection

---

## Implementation Roadmap

### Phase 1: Core Refactoring (Foundation)
1. Implement `Tool` base class and `ToolRegistry`
2. Migrate existing tools to new system
3. Update `ToolWorker` to use registry
4. Maintain backward compatibility

### Phase 2: Configuration System
1. Project-level tool configuration
2. Settings UI for enabling/disabling tools
3. Per-tool settings support
4. Load/save configuration

### Phase 3: Enhanced Existing Tools
1. Web Reader improvements (JS rendering, caching)
2. Search tool enhancements (filters, result count)
3. Wikipedia improvements (full articles, languages)
4. Image search filters

### Phase 4: New Basic Tools
1. Project Search tool
2. Batch Search and Replace tool (single and multi-file)
3. DateTime tool
4. Calculator tool
5. Dictionary tool

### Phase 5: Advanced Tools
1. Derpibooru/Imageboard tool
2. Git operations tool
3. Code execution tool (with sandboxing)
4. Translation tool

### Phase 6: Polish
1. Tool composition/chaining
2. Structured results
3. Access control system
4. Performance monitoring
5. Tool documentation generator

---

## Configuration Examples

### Minimal Setup (Basic Writing)
```json
{
    "enabled_tools": ["WIKI", "DEFINE", "DATETIME"]
}
```
, "BATCH_REPLACE", "BATCH_REPLACE_MULTI"],
    "tool_settings": {
        "GIT": {"read_only": true},
        "PYTHON_EXEC": {"timeout": 5, "require_confirmation": true},
        "BATCH_REPLACE_MULTI": {
            "max_files": 50,
            "require_confirmation": true,
            "exclude_patterns": ["*.pyc", "__pycache__/*", ".git/*"]
        
    "enabled_tools": ["SEARCH", "WEB_READ", "WIKI", "PROJECT_SEARCH", "TRANSLATE"],
    "tool_settings": {
        "SEARCH": {"max_results": 15},
        "WEB_READ": {"max_length": 20000, "enable_js": true}
    }
}
```

### Visual Creative Project
```json
{
    "enabled_tools": ["IMAGE", "DERPIBOORU", "PROJECT_SEARCH"],
    "tool_settings": {
        "DERPIBOORU": {
            "api_key": "your_key_here",
            "default_filter": "safe",
            "max_results": 20
        },
        "IMAGE": {"max_results": 15}
    }
}
```
- Special precautions for batch operations:
  - Preview changes before applying
  - File count limits (prevent accidental mass-edit)
  - User confirmation required
  - Automatic backup of modified files

### Development Project
```json
{
    "enabled_tools": ["SEARCH", "WEB_READ", "PROJECT_SEARCH", "GIT", "PYTHON_EXEC"],
    "tool_settings": {
        "GIT": {"read_only": true},
        "PYTHON_EXEC": {"timeout": 5, "require_confirmation": true}
    }
}
```

---

## Security Considerations

### Network Tools
- Respect robots.txt
- Rate limiting to avoid abuse
- User-Agent identification
- HTTPS verification
- Timeout protections

### Code Execution
- Sandboxed environment (Docker, RestrictedPython)
- Resource limits (CPU, memory, time)
- No network access by default
- Whitelist of allowed modules
- User confirmation required

### File System Access
- Restrict to project directory
- No access to system files
- Audit log of file operations
- Backup before destructive operations

### API Keys
- Store in project config (git-ignored)
- Never log or expose in chat
- Per-tool key management
- Secure storage (keyring integration)

---

## Testing Strategy

### Unit Tests
- Each tool should have comprehensive tests
- Mock external dependencies (network, APIs)
- Test error handling paths
- Test with missing dependencies

### Integration Tests
- Test tool registry operations
- Test tool invocation flow
- Test result handling
- Test configuration loading

### User Testing
- Verify tool instructions are clear to LLM
- Test with multiple LLM providers
- Measure tool usefulness
- Gather feedback on missing tools

---

## Documentation Needs

### For Developers
- Tool API reference
- How to create custom tools
- Tool lifecycle documentation
- Testing guidelines

### For Users
- Available tools and their uses
- How to enable/disable tools
- How to configure tools
- Privacy and security implications
- Troubleshooting guide

---

## Future Considerations

### OpenAI Function Calling
When using OpenAI models, leverage native function calling instead of string patterns:

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for information",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"]
            }
        }
    }
]
```

This provides:
- Structured input/output
- Better reliability (no parsing errors)
- Parallel tool calls
- Built-in validation

### Anthropic MCP Integration
Consider integrating with Anthropic's Model Context Protocol for standardized tool interfaces.

### LangChain/LlamaIndex Integration
Potential future migration to established frameworks for tool management and orchestration.
