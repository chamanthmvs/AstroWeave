# 06. Tools and Handoffs: From a Python Function to an Agent Capability

[Book home](ASTROWEAVE_BOOK.md) | Previous: [05. LLM Calls and Prompts](book/05-llms-and-prompts.md) | Next: [07. Chart Service and HTTP](book/07-chart-service.md)

**Audience:** Someone who is new to programming, Python, AI agents, and this repository
**Purpose:** Explain the tool contracts and registries, direct Python calls, and what does (and does not) happen when an LLM is expected to call a tool.
**Status:** Explanatory guide to the implementation currently in the repository. Source code is the final authority if it changes.

This is chapter 06 of the [AstroWeave beginner's book](ASTROWEAVE_BOOK.md). Read chapters 01–05 first for the system map, request lifecycle, Python syntax, graph behavior, and LLM calls; then return here for tool details.

## 1. The Short, Important Answer

A Python function runs when Python code calls it. For example, `add(2, 3)` directly calls the function named `add`. An AI model does not reach into the Python process and execute arbitrary functions by itself.

A model-driven tool system normally works like a carefully controlled relay:

1. The application tells the model which tools exist and what inputs each accepts.
2. The model responds with a structured request such as “call `lookup_weather` with `city="Pune"`.”
3. Application code recognizes that request, looks up the named tool in an allow-list, checks its inputs, and calls the Python function.
4. The application sends the function's result back to the model.
5. The model uses that result to produce an answer or request another tool.

**AstroWeave does not currently have that model-to-tool relay for specialist tools.** It has tool-related building blocks, but the specialist graph does not send tool definitions to the model, read tool-call requests from the model, invoke registered tools, or loop back after a tool result.

What it does have today:

- A `FunctionTool` wrapper that lets ordinary Python call a decorated function with `tool_name(arguments)` and checks the returned Pydantic model.
- `PromptTool` objects that store analysis instructions. They are descriptions, not executable functions.
- Per-specialist registries containing prompt-only tools, such as career analysis instructions.
- A chart client that the dispatcher calls directly. That Python function sends an HTTP request to a separate chart-service process.
- LangGraph graphs that call Python node functions in a defined workflow.
- LangChain chat-model wrappers that send prompts/messages to the configured LLM provider.

So, to the central question: **Is the agent calling the tool?** Not in the sense of an LLM selecting and executing one of the registered specialist tools. Python code calls the chart client directly. The registered specialist prompt-tools are currently not used by the specialist executor. A decorated `FunctionTool` can be called directly by Python, but the live specialist graph does not call one.

## 2. A Mental Picture

Imagine a small service company:

- The **user** is a customer describing a request.
- The **FastAPI connector** is the front desk. It checks identity, loads account information and conversation history, and passes a work order onward.
- The **orchestrator graph** is a coordinator. It asks an LLM which specialist departments are relevant and decides the order in which work should happen.
- A **specialist graph** is a department's procedure. It prepares the information, asks its configured LLM for an analysis, and records the response.
- The **chart service** is an outside laboratory. The main application sends it a request over HTTP and receives calculated chart data.
- A **tool function** is a particular permitted action, like asking the laboratory for a chart or searching a trusted source.
- A **tool registry** is an approved-action directory. Having an action listed in the directory does not mean the model has been told about it, nor that any code will execute it.

The distinction in the last bullet is crucial. A phone directory is not a phone call. Registration makes a tool findable to code that consults the registry; registration alone does not cause the LLM to call it.

## 3. A Few Words That Sound More Mysterious Than They Are

| Word | Plain-language meaning in this project |
|---|---|
| Python function | A named piece of code that can be run, usually by writing its name followed by parentheses and arguments. |
| Call / invoke | Run a function or model. `f(x)` is a call. |
| LLM / model | A program accessed through a provider API that generates text or structured responses from input messages. It is not the Python interpreter. |
| Agent | In this repository, a named specialist definition: name, description, prompt, and tool registry. It is not a separate person or necessarily a separate process. |
| Tool | An explicitly described capability. Here the word covers both callable function wrappers and non-executable prompt descriptions, so always check the concrete class. |
| Registry | A Python lookup table keyed by names. It makes registered items available to code that looks them up. |
| Framework | Reusable software that supplies common machinery. LangGraph manages graph execution; LangChain supplies message and model abstractions. Neither framework magically executes every function in the repository. |
| Graph / node | A graph is a workflow. A node is a Python function the graph runs at a particular step. Edges decide what step follows. |
| State | Data passed through graph steps, such as the question, chart, and specialist results. |
| Context | Request-scoped supporting data passed alongside the state, such as the authenticated username and birth details. |
| HTTP | A standard request-and-response protocol used here to communicate between separate processes. |
| Pydantic model | A Python class used to describe and validate structured data. |
| Decorator | Python syntax that applies a function to another function when the module is loaded. In this project, `@tool(...)` replaces the local function name with a callable wrapper object. |

## 4. The Whole Reading, From User to Answer

The common path starts when a signed-in user submits a question in Streamlit. The connector owns authentication, request IDs, history, persistence, and routing. The high-level path is:

```text
User
  -> Streamlit UI
  -> FastAPI connector (/run)
  -> orchestrator LangGraph
  -> classifier LLM chooses registered specialists
  -> task planner creates dependency stages
  -> dispatcher gets chart data from chart_service over HTTP
  -> specialist graph(s), local or remote
  -> specialist LLM produces analysis JSON
  -> orchestrator LLM synthesizes successful findings
  -> connector persists the turn and returns the answer
```

This is a workflow of Python calls plus network calls. It is not one autonomous model roaming through the source code.

### 4.1 The orchestrator asks for a routing decision

The orchestrator's `classify-request` node builds messages from the user's question, bounded prior conversation, and a small note about whether birth details are available. It calls `get_llm("orchestrator")`, then calls the model through `invoke_json_response(...)`.

The model is asked for structured routing information: specialist names, a methodology, reasoning, and optionally dependency information. The Python code then filters model-suggested names against `SPECIALIST_REGISTRY`. That check matters: text generated by a model is data, not permission to execute any arbitrary name it invents.

The classifier selects *which specialist graph to run*. It does not select a `career_role_fit` PromptTool. No specialist tool metadata is sent in this classifier request.

### 4.2 The planner orders specialist work

The planner validates the dependency information and derives stages. Independent specialists can run in the same stage; a specialist that depends on an earlier result waits for a later stage. This is normal application logic in Python, not a tool decision made by the model at execution time.

The graph's `run-stage` node calls `_get_chart_data(...)`, then calls `execute_specialist(...)` for runnable specialists. Independent work in a stage can be submitted to a Python `ThreadPoolExecutor`.

### 4.3 The dispatcher obtains chart data directly

The dispatcher gets birth details from request context and directly calls:

```python
get_birth_chart(**birth_details)
```

The `**` syntax passes dictionary entries as named function arguments. For example, `{"date": "2000-01-02", "time": "12:30:00"}` is conceptually passed as `get_birth_chart(date="2000-01-02", time="12:30:00")`, along with the other required details.

Inside `get_birth_chart`, ordinary Python builds a JSON payload and uses `httpx.post(...)` to make an HTTP request to the chart service's `/chart` endpoint. The chart service computes the chart and returns JSON. The client converts the HTTP response body to a Python dictionary. The dispatcher stores that data in graph state and shares it with specialists.

This call is sometimes casually called a “tool” because it gives the application a capability. More precisely, it is a normal Python client function directly invoked by dispatcher code. The LLM does not request it. The chart client is not registered in a specialist's tool registry and is not exposed to the model as a callable tool schema.

### 4.4 The dispatcher hands the work to a specialist graph

For local execution, `execute_specialist(...)` makes a handoff dictionary containing the question, prior messages, specialist name, methodology, chart data, and required dependency results. It invokes the compiled graph with:

```python
_get_specialist_graph().invoke(handoff, context=runtime.context)
```

Read this as: “Run the specialist workflow using this initial data, and make this request context available to its nodes.” The `.invoke(...)` here is LangGraph's graph-running API. It does **not** mean “invoke a registered FunctionTool.” The same word is used for different operations; the object before `.invoke` tells you which one is happening.

If that specialist is configured in `ASTROWEAVE_SPECIALIST_URLS`, the dispatcher instead sends the handoff to a specialist HTTP service. That service runs its own specialist graph. Local graph invocation and remote HTTP invocation are two transports for specialist work; neither is model-directed tool execution.

### 4.5 The specialist graph calls its LLM

The specialist graph looks up the `AgentDefinition` by `current_task`. It takes `agent.prompt`, combines it with the question, methodology, chart JSON, history, and dependency findings, then calls the configured specialist LLM.

The actual call is the chat model's `.invoke([...])` inside the JSON-response helper. The messages include a system message (the specialist's instructions) and a human message (the task data). The application parses the model's JSON text and stores fields such as `analysis`, `conclusion`, and `confidence` in `specialist_results`.

Notice what this code does **not** read: `agent.tools`. The registry is present on the agent definition, but this executor does not inspect it. It also does not look for a `tool_calls` property in the model response. The specialist therefore cannot choose one of those registry entries through this path.

### 4.6 The orchestrator writes the final response

After all stages have finished, the orchestrator passes successful specialist findings to its synthesis LLM call. The connector then persists the user question and final answer and returns them to Streamlit.

Conversation persistence is another Python/database operation. It is separate from LangChain model invocation and separate from specialist tools.

## 5. The Three Things Often Confused as “Tool Calling”

| Example | What actually calls it? | Does an LLM choose it? | What happens? |
|---|---|---:|---|
| `FunctionTool` made with `@tool(...)` | Python, using `my_tool(...)` or `my_tool.invoke(...)` | No, not by itself | Wrapper calls the underlying Python function and checks the response type. |
| A `PromptTool` in `CAREER_TOOLS` | Nothing in the current specialist runtime | No | Stores an intent label and prompt text; its `invoke()` deliberately raises an error. |
| `get_birth_chart(...)` | Dispatcher Python code | No | Sends an HTTP POST to the separate chart service and returns its JSON. |
| `_get_specialist_graph().invoke(...)` | Dispatcher Python code | No | LangGraph runs the specialist graph. This is graph invocation, not a registered tool call. |
| `llm.invoke(messages)` | Specialist or orchestrator Python node | No tool choice here | LangChain's chat-model object sends messages to the configured provider and returns a model response. |

A provider/model can support tool calling as a capability and still not use it in this application. The application must explicitly define and expose tool schemas, handle the model's structured tool-call response, execute the approved function, and give the result back to the model.

## 6. How a Plain Python Function Call Works

Suppose Python has this function:

```python
def greet(name: str) -> str:
    return f"Hello, {name}!"
```

The `def` statement creates a function object and binds it to the name `greet`. The indented body does not run yet. This line runs it:

```python
message = greet("Maya")
```

Python looks up the object named `greet`, supplies the value `"Maya"` for its `name` parameter, executes the function body, and binds its returned string to `message`.

The name can be stored in another variable too:

```python
chosen_function = greet
message = chosen_function("Maya")
```

The function object is a value. Calling it still requires parentheses. The AstroWeave `FunctionTool` wrapper uses this same Python behavior: it is an object with a `__call__` method, so `some_tool(...)` is shorthand for its controlled invocation method.

## 7. `base.py`: What the Function-Tool Wrapper Does

The implementation lives in `src/astroweave/common/tools/base.py`. The following explains its pieces in source order. It is close to a line-by-line tour, while grouping syntax that serves one purpose.

### 7.1 Imports and type helpers

- `from __future__ import annotations` lets this file defer evaluation of many type annotations. This helps with forward references and modern typing syntax.
- `inspect` is used to examine the wrapped function's signature, such as its parameter names.
- `ABC` and `abstractmethod` support abstract base classes: a shared contract that is not itself a complete tool.
- `Callable` describes a value that can be called like a function. `ParamSpec` and `TypeVar` preserve useful type information through the decorator. `Any` is used where the common wrapper accepts arbitrary arguments.
- `Enum` creates a fixed set of named values.
- `update_wrapper` copies identifying attributes such as the original function's name and documentation onto the wrapper.
- `BaseModel` and `ConfigDict` come from Pydantic and define validated structured data.

The type declarations `Parameters = ParamSpec(...)` and `ReturnType = TypeVar(...)` are hints for static type checkers. They do not call functions or create runtime tool behavior.

### 7.2 The shared response model

```python
class BaseToolReturnType(BaseModel):
    success: bool
    error: str | None = None
```

This class defines the minimum response shape for an executable function tool. A response must say whether the action succeeded; an error message is optional. A specific tool can subclass it and add fields, such as a search result or computed value.

Creating a Pydantic model instance, for example `BaseToolReturnType(success=True)`, creates structured data. It does not run a tool.

### 7.3 The kind and description of a tool

`ToolType` is a string enum. The current values are `FUNCTION` and `PROMPT`. A function tool has executable Python behind it. A prompt tool holds instructions and is not executable code.

`ToolMetadata` records `name`, human/model-facing `description`, `type`, optional response-model class `returns`, and optional `intent`. The `ConfigDict(arbitrary_types_allowed=True)` setting permits `returns` to be a Python class object, rather than only ordinary JSON-like data.

Metadata describes a capability; it does not run it, register it automatically with an LLM provider, or guarantee the description has been sent to a model.

### 7.4 The abstract base contract

`BaseTool` says that every concrete tool must provide:

- A `metadata` property describing the tool.
- An `invoke(*args, **kwargs)` method that performs the action and returns a `BaseToolReturnType`.

The `@property` makes `metadata` look like an attribute when read. `@abstractmethod` marks required methods. The `raise NotImplementedError` lines are placeholders for subclasses; code should not try to use this base class directly.

`*args` means any number of positional arguments; `**kwargs` means any number of named arguments. They make a common interface possible even when individual functions have different parameters.

### 7.5 `FunctionTool`: wrapping and calling a real function

The constructor receives two things: the real Python function and its `ToolMetadata`. It stores them as `_function` and `_metadata`. The leading underscore is a Python naming convention meaning “internal use”; it is not access control.

`update_wrapper(self, function)` copies helpful function identity information onto the wrapper. The `metadata` property returns the stored description. The `signature` property uses `inspect.signature(self._function)` to report the original function's call shape. This signature is inspectable metadata; this implementation does not itself validate or coerce arguments against that signature.

The central method is:

```python
result = self._function(*args, **kwargs)
```

That is the point where the underlying Python function actually runs. `FunctionTool.invoke(...)` passes through the supplied positional and named arguments, receives the return value, then checks:

```python
isinstance(result, self.metadata.returns)
```

If the return value is not an instance of the declared response model, it raises `TypeError`. If it is the right type, it returns that result unchanged. This is a return-contract check, not an LLM handoff and not full input validation.

Finally, `__call__` delegates to `self.invoke(...)`. Python calls an object's `__call__` method when the object is used with parentheses. Therefore both forms work:

```python
result = focus_tool.invoke(question="promotion")
result = focus_tool(question="promotion")
```

Both reach `FunctionTool.invoke`, and then the wrapped function. The wrapper makes this call possible; the model does not.

### 7.6 `PromptTool`: deliberately not a function

`PromptTool` builds metadata with type `PROMPT`, puts the prompt text in the description, and stores an intent label. Its `invoke(...)` raises `RuntimeError` saying it is descriptive only and cannot be invoked.

This is an intentional guard against mistaking analytical instructions for executable Python. A sentence like “Assess promotion indicators” is text. It needs to be inserted into an LLM prompt by application code to influence a model; it cannot be executed with Python as though it were a function body.

### 7.7 The `@tool` decorator

The `tool(...)` function is a decorator factory: calling `tool(description=..., returns=...)` first creates and returns an inner `decorator` function. Python then applies that returned decorator to the function beneath `@tool`.

For example:

```python
@tool(
    name="career_focus",
    description="Find the strongest career theme.",
    returns=CareerFocusResult,
)
def career_focus(question: str) -> CareerFocusResult:
    return CareerFocusResult(success=True, focus=question)
```

Python processes this roughly like:

```python
def career_focus(question: str) -> CareerFocusResult:
    return CareerFocusResult(success=True, focus=question)

career_focus = tool(
    name="career_focus",
    description="Find the strongest career theme.",
    returns=CareerFocusResult,
)(career_focus)
```

The final name `career_focus` now refers to a `FunctionTool` object wrapping the original function, rather than directly referring to the original function object. The wrapper is callable because it implements `__call__`. Calling `career_focus(question="... ")` reaches the original function through the wrapper.

The decorator chooses the explicit `name` when provided; otherwise it uses `function.__name__`. It creates `ToolMetadata`, then returns a `FunctionTool` around the original function. The overload declarations above the implementation help static type checking; they do not create separate runtime behavior.

**Important boundary:** this decorator does not call a LangChain registration API, does not contact an LLM, and does not make the tool available to a model. It creates a local Python wrapper with metadata.

## 8. Registries: A Directory Is Not an Execution Engine

`ToolRegistry` stores tools in a dictionary keyed by `metadata.name`.

- `register(tool)` gets the name from metadata, rejects a duplicate with `ValueError`, saves the object, and returns it.
- `get(name)` returns the tool or `None` if there is no match.
- `require(name)` returns the tool or raises `KeyError` if it is missing. This is useful when missing a required tool should be treated as a programming/configuration error.
- `metadata()` returns descriptions for all registered tools.
- `metadata_for_intents(...)` selects descriptions whose intent matches one of the supplied intent labels.
- `grouped_metadata()` organizes descriptions by intent.
- `__contains__`, `__iter__`, and `__len__` make normal Python operations such as `"lookup" in registry`, `for item in registry`, and `len(registry)` work.

The registry has no LLM connection and no automatic behavior. Nothing happens merely because an item is inserted into its dictionary. Some other code must retrieve the item and then call it.

`AgentDefinition` groups a specialist's `name`, `description`, `prompt`, and `ToolRegistry`. `AgentRegistry` similarly stores definitions by name and prevents duplicate agents. `SPECIALIST_REGISTRY` is the project-wide catalog of career, finance, love, and sports specialists.

At the time this guide was written, each specialist registry contains prompt-only intent descriptions. Tests verify four intent groups and twelve entries per specialist. That is different from twelve executable Python functions: these entries are `PromptTool` instances.

## 9. The Exact Specialist Tool Gap

The specialist executor currently follows this essential sequence:

1. Read `current_task`, such as `"career"`.
2. Look up `SPECIALIST_REGISTRY.get(specialist_name)`.
3. If no agent exists, return a state update with an error.
4. Build `user_content` with the question, methodology, prior conversation, dependency findings, and chart data.
5. Get an LLM using `get_llm("specialist", agent_name=specialist_name)`.
6. Call `invoke_json_response(...)` with the agent's system prompt and the user content.
7. Put parsed analysis, conclusion, and confidence in `specialist_results`.

There is no step between 4 and 6 that converts `agent.tools` into model-visible tool schemas. There is no step after 6 that examines a model-requested tool name, finds it in a registry, calls it, adds a tool-result message, and asks the model again.

The current code reads `agent.prompt`; it does not read `agent.tools`. Consequently, the career prompt-tools do not currently affect the specialist model call. Their metadata is registered and testable, but selection/use in the live graph is not implemented.

The specialist graph has nodes named planner, executor, collector, evaluator, and synthesizer. The executor makes the real LLM request. The other nodes are currently no-op or fixed-result scaffolding; the evaluator marks the single pass sufficient. A graph node called “planner” is not automatically an LLM planner, and a node called “tool” would not automatically execute a tool unless its Python function did that.

## 10. What a Real Model-Requested Function Handoff Would Need

This section describes a possible design, **not current AstroWeave behavior**. It helps make the missing link visible.

A model-directed tool loop needs code for every relay step:

```text
Python constructs approved tool descriptions and input schemas
  -> model request includes those descriptions
  -> model returns either final text or structured tool-call request(s)
  -> application validates tool name and arguments
  -> application invokes only a registered, allowed function
  -> application records the tool result with the matching request ID
  -> application sends that result to the model
  -> model returns final text or another tool request
```

A conceptual Python sketch might look like this (it is illustrative pseudocode, not an existing implementation):

```python
while True:
    response = model_with_tools.invoke(messages)

    if not response.tool_calls:
        return response.content

    for requested_call in response.tool_calls:
        registered_tool = agent.tools.require(requested_call["name"])
        arguments = validate_arguments(registered_tool, requested_call["args"])
        result = registered_tool.invoke(**arguments)
        messages.append(make_tool_result_message(requested_call, result))
```

Real production code also needs to handle provider-specific response formats, malformed or extra arguments, tool errors, authorization, timeouts, sensitive data, repeated calls, maximum tool-call counts, and what to do if a tool fails. The tool name must be looked up in a trusted allow-list. Never execute a function name supplied by the model using `globals()`, `eval()`, or a similar unrestricted mechanism.

LangChain may provide model-binding and tool-execution helpers for compatible models, while LangGraph may represent the loop with conditional edges and a tool-execution node. Those are implementation options, not behavior that appears automatically because the packages are installed. AstroWeave's custom `FunctionTool` is not itself shown being bound to the current model in the specialist graph.

## 11. Framework Responsibilities, Separately

### LangGraph

AstroWeave uses `StateGraph` to define named Python nodes, connect them with edges, route conditionally, pass state between steps, and compile a runnable graph. Calling the compiled graph's `.invoke(...)` starts that workflow. LangGraph runs the node functions the application registered; it does not infer that every registry entry should run.

The orchestrator graph coordinates classification, task planning, staged specialist execution, and synthesis. A specialist graph coordinates a single specialist's current process.

### LangChain

AstroWeave uses LangChain message classes such as `SystemMessage` and `HumanMessage`, and provider-specific chat model classes behind the common `get_llm(...)` factory. The node calls a chat model with `.invoke(messages)` or through `invoke_json_response(...)`. The model wrapper handles provider communication and response conversion.

The existence of a chat model object does not mean tools have been attached to it. In the current specialist path, code does not call `bind_tools(...)` and does not process model `tool_calls`.

### Python application code

Python decides which nodes to build, how to route tasks, when to call the chart client, which specialist to look up, what messages to send, how to parse responses, how errors are recorded, and what results are returned. This is the control plane that connects the components.

### External services

The LLM provider and chart service are separate processes/services. The application sends them requests over network protocols. The Python function initiating a request runs locally; the remote service handles its own work and sends a response back.

## 12. State Versus Context

Graph **state** is the working record that nodes update: query, selected specialists, chart data, specialist results, errors, and final answer. Some state fields have reducers. For example, `specialist_results` and `errors` append updates instead of replacing the earlier lists. This lets multiple tasks contribute results.

Runtime **context** carries supporting request-scoped information such as username and birth details. The dispatcher reads birth details from context to call the chart service. The specialist graph receives context as well, but its main analysis input is assembled into state-derived messages.

An analogy: state is the shared work order that gets annotations as the job progresses; context is the sealed envelope of request facts accompanying the work order. Both are ordinary Python data structures described with type annotations. Type annotations help people and tools understand intended values; they are not by themselves a security boundary or runtime permission system.

`tool_results` exists in the graph state type as a reserved field. Its presence does not show that a tool loop is active. A field can be prepared for future use without any current code writing to it.

## 13. Error Handling in the Handoff

Different boundaries fail differently:

- Missing birth details prevent chart calculation and produce a state error.
- HTTP failures from the chart service are caught by dispatcher code and reported as errors.
- An unknown specialist name produces an error instead of an arbitrary lookup or execution.
- A context-size limit can reject an oversized handoff when configured.
- Malformed model JSON is retried by the shared JSON-response helper and ultimately reported as an error when parsing fails.
- A specialist failure is captured so unrelated specialists may still run.
- If there are successful specialist results, synthesis can use them even when another task had an error.

A future tool loop would need its own error behavior too. A tool returning `success=False` is still a normal Python return value; the loop must decide whether to show that result to the model, retry, stop, or turn it into a user-facing error.

## 14. How to Trace This Yourself

A productive way to explore the code is to follow one call at a time:

1. Find the API `/run` handler and identify where it invokes the orchestrator or direct specialist route.
2. Find `build_orchestrator_graph()` and read the node/edge definitions.
3. Follow the `run-stage` node into `execute_specialist(...)`.
4. Follow the chart branch into `get_birth_chart(...)` and its `httpx.post(...)`.
5. Follow local specialist execution into `_get_specialist_graph().invoke(...)`.
6. In the specialist graph, find the executor's registry lookup and model call.
7. Search for `bind_tools`, `ToolNode`, `tool_calls`, and `agent.tools` use. The absence of a tool-execution path is part of the current finding, not a hidden framework behavior.
8. Read `tests/unit/test_tools.py`: it proves direct wrapper invocation and return-type checking. Read `tests/unit/test_agent_registry.py`: it proves tools are registered and grouped. These tests do not prove that an LLM can call them.

A useful debugging question is “What exact Python line calls this object?” If you cannot find a direct call or framework node that receives the object, then registration alone is not execution.

## 15. Source Map

| Area | What to read it for |
|---|---|
| `app/streamlit_app.py` | User-facing forms and request submission. |
| `src/astroweave/api/main.py` | HTTP routes, authentication boundary, request orchestration, and persistence. |
| `src/astroweave/graphs/orchestrator/orchestrator_graph.py` | Request classification, dependency planning, stage execution, and synthesis. |
| `src/astroweave/orchestration/dispatcher/dispatcher.py` | Chart retrieval and local/remote specialist handoff. |
| `src/astroweave/graphs/specialist/specialist_graph.py` | Specialist lookup, prompt assembly, LLM call, and result creation. |
| `src/astroweave/agents/registry.py` | Agent definition and catalog behavior. |
| `src/astroweave/agents/specialists/__init__.py` | Built-in specialist definitions and their tool registries. |
| `src/astroweave/agents/specialists/career/tools.py` | Concrete example of prompt-only registered career tools. Other domains follow the same pattern. |
| `src/astroweave/common/tools/base.py` | Base contracts, function wrapper, prompt wrapper, and decorator. |
| `src/astroweave/common/tools/registry.py` | Named per-agent tool lookup. |
| `src/astroweave/common/tools/chart_client.py` | Direct HTTP chart client. |
| `src/astroweave/common/state/state.py` | Data shape passed through graph nodes. |
| `src/astroweave/common/context/context.py` | Request-scoped context shape. |
| `src/astroweave/common/llm/factory.py` and `providers.py` | Model configuration entry point and provider builders. |
| `tests/unit/test_tools.py` | Direct function-wrapper and registry behavior. |
| `tests/unit/test_agent_registry.py` | Built-in agents and registered prompt-tool counts. |

## 16. Quick Questions and Answers

**If a tool is a function, why not just call `a()`?**

That is exactly how ordinary Python calls a function. A `FunctionTool` also supports parentheses because its `__call__` method forwards to `invoke()`. What is missing is not Python's ability to call it; it is the model-to-application relay that would decide *which* registered function to call and with *which* arguments.

**Does the model call Python?**

No. The model sends a response to the application. The application's Python code may interpret a structured part of that response as a request and call an approved function. AstroWeave's current specialist execution path does not implement that interpretation for its registered tools.

**Does LangChain call the tool?**

Not in the code path described here. LangChain wraps chat models and messages. Tool calling requires explicit binding/execution code or a graph path that handles tool calls.

**Does LangGraph call the tool?**

LangGraph calls the Python node functions that were added to its graph. The current specialist graph has no tool-execution node or model-tool loop. It does call the specialist executor node, which calls the LLM.

**Is the chart service a tool?**

In a broad architectural sense, it is an application capability. In the precise runtime sense, the dispatcher directly calls a Python HTTP client; the LLM does not request that action.

**Are career tools empty?**

No. The career registry contains twelve `PromptTool` entries grouped by four intents. They are not Python functions, and the current specialist executor does not use the registry entries. The other specialist registries use the same prompt-only pattern.

**What does “invoke” mean?**

It depends on the object. `graph.invoke(...)` runs a LangGraph workflow. `llm.invoke(...)` requests a model response. `function_tool.invoke(...)` runs a wrapped Python function. Same method name, three different objects and jobs.

**What does the decorator do?**

It turns a plain function into a callable wrapper that stores metadata and checks its return model. It does not connect the function to an LLM.

## 17. A Reliable Summary to Keep in Mind

There are two separate decisions:

1. **Who calls the Python function?** In the current chart path, dispatcher code calls it. In a direct `FunctionTool` example, the Python caller calls it. The LLM does not execute local Python.
2. **Who chooses which function to call?** In the current registered specialist tools, nobody: the model is not shown those tools and the execution loop is absent. In a future tool-enabled path, the model could request a named action, but Python must validate and execute that request.

That separation is the key to understanding AstroWeave's current tool handoff. The function is ordinary Python. The framework supplies useful workflow and model abstractions. The application code must explicitly connect model requests to safe function calls, and that connection is not yet present for specialist tools.

## Continue

Next: [07. Chart Service and HTTP](book/07-chart-service.md). Return to the [book home](ASTROWEAVE_BOOK.md) for the full chapter list.
