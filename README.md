# webfunction-python

A reference client library for the [Web Function (wfn)](https://webfunction.org) protocol.

Part of the same reference-client suite as the Ruby gem
(`https://github.com/webfunction-protocol/webfunction-ruby`, the spec author's own implementation),
`webfunction-go`, `webfunction-java`, and `webfunction-csharp`.

## Install

```bash
pip install webfunction
```

The only runtime dependency is [httpx](https://www.python-httpx.org/), which is what
lets this library offer both a synchronous `Client` and an async `AsyncClient` from a
single implementation.

## Usage

### Sync

```python
from webfunction import Client

client = Client.from_package_endpoint("https://api.example.com/package")
result = client.list_items(email="a@example.com")  # dynamic dispatch, no generated code
```

### Async

```python
import asyncio
from webfunction import AsyncClient

async def main():
    client = await AsyncClient.from_package_endpoint("https://api.example.com/package")
    result = await client.list_items(email="a@example.com")

asyncio.run(main())
```

### Pagination

Endpoints that declare the `paginated` flag return a `Page` (or `AsyncPage`):

```python
page = client.list_people()
for person in page:
    ...
if page.has_next:
    page = page.next_page()
```

### Pipelining

If the package declares a `pipeline_url`, pass `pipelined=True` to batch several
endpoint invocations into a single request. Calls return a `Promise` instead of
executing immediately; index into a promise (`promise["id"]`) to build a reference to
one of its fields before it's resolved.

```python
client = Client.from_package_endpoint(url, pipelined=True)
item = client.list_items(email="a@example.com")
detail = client.get_widget(id=item["id"])  # references item's future "id" field
results = client.pipeline.execute()
print(detail.value)
```

### Errors

All errors are subclasses of `WebFunctionError`, carrying `.code`, `.message`, and
`.details`: `BadRequestError`, `UnexpectedStatusCodeError`, `JsonParseError`,
`UnresolvedPromiseError`.

## A note on unknown fields

This library never validates incoming JSON against a strict schema -- model classes
only read the keys they know about via plain `dict.get()`, so an API that adds an
undocumented field to its responses (this has happened for real against
`api.reservepay.com`) won't break parsing the way it did for the Java client, which
needed an explicit fix to disable strict unknown-field rejection.

## Development

```bash
pip install -e .
python -m unittest discover tests
```
