# 03. Python Foundations: Reading the Syntax in AstroWeave

[Book home](../ASTROWEAVE_BOOK.md) | Previous: [02. One Request](02-one-request.md) | Next: [04. Graphs and Shared Data](04-graphs-and-state.md)

## The question this chapter answers

What does the Python syntax mean when I encounter it in a real AstroWeave file, and how do I tell a definition from something that is actually running?

This is a practical tour, not a complete Python course. Each example points to a pattern used in this repository.

## 1. The fundamental distinction: define versus run

```python
def calculate_total(price: float, tax: float = 0.0) -> float:
    return price + tax
```

This defines a function object called `calculate_total`. The body does not run yet. This runs it:

```python
invoice_total = calculate_total(100.0, tax=8.0)
```

Read the call as:

1. Find the object named `calculate_total`.
2. Pass `100.0` as `price` and `8.0` as `tax`.
3. Run the indented statements.
4. Take the value after `return` and assign it to `invoice_total`.

At the end, `invoice_total` is `108.0`. The function can run only because some code called it. Merely defining or registering a function does not execute it.

## 2. Parameters, arguments, return values

- A **parameter** is a name in the function definition, such as `price`.
- An **argument** is the concrete value supplied at a call site, such as `100.0`.
- A **return value** is what the function gives back to its caller.

```mermaid
flowchart LR
    Call[calculate_total(100.0, tax=8.0)] --> Bind[price = 100.0, tax = 8.0]
    Bind --> Body[Run function body]
    Body --> Return[Return 108.0]
    Return --> Caller[invoice_total receives 108.0]
```

In AstroWeave, compare these call sites:

| Expression | Object receiving the call | Effect |
|---|---|---|
| `get_birth_chart(**birth_details)` | Python function | Sends an HTTP request to chart service and returns decoded JSON. |
| `_specialist_graph.invoke(handoff, context=...)` | Compiled LangGraph graph | Runs the graph's registered nodes. |
| `llm.invoke(messages)` | LangChain chat model object | Makes a model request and returns a model response. |
| `career_tool.invoke(question=...)` | AstroWeave `FunctionTool` object | Runs the wrapped Python function. |

The spelling `.invoke` is shared. The receiver determines the behavior.

## 3. Names point to objects

Python variables hold references to objects. A function can be stored in another name:

```python
def greet(name: str) -> str:
    return f"Hello, {name}!"

chosen_action = greet
message = chosen_action("Sam")
```

Here `chosen_action` refers to the same function object as `greet`. The call with parentheses runs it. This is useful because a registry can store functions or wrapper objects and later retrieve them by name.

```mermaid
flowchart LR
    Name1[greet] --> Fn[Function object]
    Name2[chosen_action] --> Fn
    Call[chosen_action("Sam")] --> Fn
```

A dictionary registry is the same idea at scale: names map to objects. It does not make those objects execute automatically.

## 4. Types in a function signature

```python
def make_label(count: int, title: str | None = None) -> str:
    ...
```

- `count: int` says the intended input is an integer.
- `title: str | None` says the value may be a string or `None`.
- `-> str` says the intended return is a string.

These annotations help editors, type checkers, and readers. Python does not generally enforce them just because they are written. Runtime validation requires explicit logic or a library such as Pydantic.

AstroWeave uses both: type annotations document graph-state shapes; Pydantic models validate HTTP bodies and tool response models.

## 5. Return statements and state updates

A function may return a regular value, or a dictionary describing changes. Graph nodes commonly return a partial state update:

```python
def _planner(state: State) -> State:
    return {"specialists": ["career"]}
```

This does not mean the function has copied every state field into the returned dictionary. It returns one update. LangGraph applies that update using the graph's state schema and reducers.

A plain `return {}` means “no state fields changed here.” It does not mean return an empty answer to the user.

## 6. Dictionaries and lists

A dictionary maps keys to values:

```python
handoff = {
    "user_query": "Will I get promoted?",
    "current_task": "career",
    "chart_data": {"d1": {}},
}
```

The dispatcher uses a handoff dictionary as input to the specialist graph. `handoff["current_task"]` reads a required key and raises `KeyError` if missing; `handoff.get("current_task", "")` reads it safely with a default.

A list is an ordered collection:

```python
specialists = ["career", "finance"]
```

`for specialist in specialists:` visits each item. A list can be appended to; a graph reducer may define how updates to a list are merged between nodes.

The `or` idiom often provides a fallback:

```python
messages = state.get("messages") or []
```

If the key is absent or its value is empty/false, `messages` becomes an empty list.

## 7. `*args`, `**kwargs`, and dictionary expansion

A function may accept flexible argument groups:

```python
def run_action(*args, **kwargs):
    ...
```

- `args` collects extra positional values into a tuple.
- `kwargs` collects extra named values into a dictionary.

A function call can expand a dictionary of named inputs:

```python
birth_details = {
    "date": "1990-01-01",
    "time": "10:00:00",
    "latitude": 13.08,
    "longitude": 80.27,
    "utc_offset_hours": 5.5,
}
get_birth_chart(**birth_details)
```

This is similar to writing:

```python
get_birth_chart(
    date="1990-01-01",
    time="10:00:00",
    latitude=13.08,
    longitude=80.27,
    utc_offset_hours=5.5,
)
```

The names in the dictionary must match accepted parameter names. Python itself raises an error if a required argument is absent or an unexpected argument is supplied.

## 8. Importing code from another file

```python
from astroweave.common.tools import PromptTool
```

This asks Python to load the module `astroweave.common.tools` and bind the name `PromptTool` in the current file. Package `__init__.py` files can re-export names so callers do not have to import from a deeply nested module.

An import is not a function call. However, Python executes a module's top-level statements the first time it imports that module. For example, provider registration at the bottom of `providers.py` happens when that module is imported. A function body still waits until called.

## 9. Classes, instances, and methods

A class is a recipe for creating objects. An instance is one concrete object made from that class.

```python
class Counter:
    def __init__(self, start: int):
        self.value = start

    def increment(self) -> int:
        self.value += 1
        return self.value

counter = Counter(3)
next_value = counter.increment()
```

- `Counter` is the class.
- `counter` is an instance.
- `__init__` initializes that instance.
- `self` refers to the particular instance.
- `counter.increment()` calls a method with `counter` as its instance.

`FunctionTool`, `ToolRegistry`, `AgentDefinition`, and `ConversationStore` are classes used to create objects with stored data and behavior.

## 10. Properties and methods

A property is accessed like a field but can run code behind the scenes:

```python
@property
def metadata(self) -> ToolMetadata:
    return self._metadata
```

Then code writes `tool.metadata`, not `tool.metadata()`. A method uses parentheses: `tool.invoke(...)`.

AstroWeave's `FunctionTool.signature` is also a property: accessing it runs `inspect.signature(...)` on the wrapped function.

## 11. Decorators: functions that transform functions

A decorator takes a function and returns something to use in its place. Python's syntax:

```python
@decorate
def work():
    ...
```

is conceptually:

```python
def work():
    ...

work = decorate(work)
```

AstroWeave's decorator takes configuration first, then returns a decorator:

```python
@tool(description="Find a career theme.", returns=CareerFocusResult)
def career_focus(question: str) -> CareerFocusResult:
    ...
```

The configured `tool(...)` call creates a decorator. That decorator receives the original function and returns a `FunctionTool` wrapper. The name `career_focus` is rebound to that wrapper. Since the wrapper implements `__call__`, it remains callable with parentheses.

A decorator can add behavior such as metadata or validation. It does not automatically connect the function to a model. See [06. Tools and Handoffs](../BEGINNER_GUIDE.md) for the full call path.

## 12. Exceptions and `try` / `except`

```python
try:
    chart = get_birth_chart(**birth_details)
except httpx.HTTPError as error:
    return {"errors": [f"Could not compute a birth chart: {error}"]}
```

The `try` block is attempted first. If an `HTTPError` occurs, Python jumps to the matching `except` block. The function turns a network failure into a structured state error instead of letting the whole application crash.

An exception not matching that `except` clause keeps propagating unless an outer caller catches it. AstroWeave has nested boundaries: the chart helper may raise, dispatcher catches service errors, and the API catches unexpected graph failures and maps them to an HTTP error response.

`raise` explicitly signals failure. `raise ... from error` preserves the original exception as the cause. `return` exits normally; `raise` does not.

## 13. Comprehensions and small transformations

```python
specialist_names = [agent.name for agent in SPECIALIST_REGISTRY]
```

This creates a list by looping over registry agents and taking each `.name`. It is equivalent to a small loop:

```python
specialist_names = []
for agent in SPECIALIST_REGISTRY:
    specialist_names.append(agent.name)
```

AstroWeave uses comprehensions to filter specialist names, build summaries, and convert SQLite rows into messages. Expand them into loops mentally if the compact form is hard to read.

## 14. Context managers: `with`

```python
with auth.get_connection() as connection:
    user = auth.get_user(connection, email)
```

A context manager sets up a resource and reliably performs cleanup when the block exits, even if an exception occurs. Here the resource is a SQLite connection/transaction context. This is safer than manually opening it and hoping every return path closes or commits correctly.

The same syntax appears for thread pools:

```python
with ThreadPoolExecutor(max_workers=len(runnable)) as pool:
    results = pool.map(execute, runnable)
```

Leaving the `with` block shuts down the pool cleanly.

## 15. Lambdas and callbacks

A callback is a function passed to another function so that it can be called later. For example, `pool.map(execute, runnable)` receives `execute` as a function value and calls it for each task.

A `lambda` is a small anonymous function, such as `lambda name: name.upper()`. AstroWeave's main workflows mostly use named functions because they are easier to inspect and log.

This is related to tool selection: storing a callable and passing it around is ordinary Python. A runtime still needs to decide when to call it.

## 16. Threading versus asynchronous Python

AstroWeave uses `ThreadPoolExecutor` for independent specialist tasks in one stage. A thread pool starts worker threads and allows calls to overlap while waiting for I/O such as LLM/network responses.

This code is not automatically `async` just because it waits on the network. `async def`, `await`, and ordinary `def` have different execution models. To understand this code, follow the actual call: the orchestrator uses a thread pool for multiple specialists; the chart client uses synchronous `httpx.post`; the APIs define synchronous route functions.

Concurrency can reduce wall-clock time, but it also means multiple result updates need deterministic collection and careful error handling. The orchestrator collects results/errors after the stage's workers finish.

## 17. Reading the tests as runnable examples

Tests can show how a function is expected to behave:

- In `tests/unit/test_tools.py`, a decorated function is called with ordinary Python parentheses. The test checks the result and rejects a wrong return type.
- In `tests/unit/test_agent_registry.py`, a registry is constructed and queried. No model is involved.
- In `tests/unit/test_orchestrator_graph.py`, `get_llm` and `execute_specialist` are patched with fakes so the test can inspect call order without network access.

A test mock is a stand-in object. It lets a test isolate behavior, but it is not proof that the real external service works.

## 18. A five-question code-reading habit

For any unfamiliar block, ask:

1. Is this a definition, or does it run now?
2. What object is being called at this line?
3. What values are passed in, and where did they come from?
4. What value or exception comes back?
5. Who consumes that return value next?

These questions are enough to untangle most Python “magic.”

## Continue

With the Python syntax in hand, go to [04. Graphs and Shared Data](04-graphs-and-state.md). For project-specific tool wrappers and LLM handoffs, see [06. Tools and Handoffs](../BEGINNER_GUIDE.md).
