# rich-table-builder

A Python library which extends [rich](https://github.com/Textualize/rich) with a declarative API
for building beautiful tables for console output.

## Overview

This library provides a declarative way to define and build tables for console output.
It builds on top of `rich.table.Table` and supports all the same arguments while adding features like:

- Automatic data extraction from objects using flexible key accessors
- Support for transposing tables (rows become columns)
- Automatic aggregation for footers (e.g., column totals)
- Customizable formatting for cells

## Installation

This package is not on PyPI, it must be installed from GitHub.

```bash
# Install using pip
pip install git+https://github.com/jbchouinard/rich-table-builder.git
# Add to poetry project
poetry add git+https://github.com/jbchouinard/rich-table-builder.git
```

## Usage

### Basic Example

```python
import rich
from richtablebuilder import TableBuilder, TableField, Obj

# Define your table structure
class CartTableBuilder(TableBuilder):
    name = TableField("Item Name", key="name", footer="Total")
    quantity = TableField("Quantity", key="quantity", footer=sum)
    price = TableField("Price", key="price", footer="-")
    subtotal = TableField("Subtotal", key=lambda item, _: item["quantity"] * item["price"], footer=sum)

# Create your data
cart = [
    {"name": "Item 1", "quantity": 1, "price": 10},
    {"name": "Item 2", "quantity": 2, "price": 20},
]

# Create a table builder and apply it to your data
my_table_builder = CartTableBuilder(show_header=True, show_footer=True)
table = my_table_builder(cart, title="Shopping Cart")

# Print the table
rich.print(table)
```

### Advanced Features

#### Nested Data Access

Use the `Obj` accessor to extract values from nested data structures:

```python
# Access nested data
user_field = TableField("User", key=Obj.user.name)
address_field = TableField("Address", key=Obj.user.address.street)

# Access list/array items
first_tag = TableField("First Tag", key=Obj.tags[0])
```

#### Custom Formatting

Apply custom formatting to values:

```python
def format_currency(value):
    return f"${value:.2f}"

price_field = TableField("Price", key="price", formatter=format_currency)
```

#### Transposed Tables

Create transposed tables where fields become rows instead of columns:

```python
data = []

# Normal table (fields are columns)
table = my_table_builder(data)

# Transposed table (fields are rows)
table_transposed = my_table_builder(data, transposed=True)
```

#### Consistent Styling by Value

Apply consistent styles to the same values:

```python
from richtablebuilder import rainbow_by_value

# Each unique value will get its own color, consistently
name_field = TableField("Name", key="name", formatter=rainbow_by_value)
```

## API Reference

### TableField

The `TableField` class defines a column (or row in transposed mode) in the table.

```python
TableField(
    header="",          # Header text or reducer function
    footer="",          # Footer text or reducer function
    key=None,           # Key, callable, or Obj expression to extract data
    default=None,       # Default value when key is not found
    formatter=str,      # Function to format values
    style="",           # Style for values
    header_style="",    # Style for header
    footer_style="",    # Style for footer
    justify="left",     # Text justification ("left", "center", "right")
)
```

### TableBuilder

The `TableBuilder` class is subclassed to define table structures.

```python
class MyTableBuilder(TableBuilder):
    # Define fields as class attributes
    field1 = TableField(...)
    field2 = TableField(...)
    # ...

# Create an instance with table options
builder = MyTableBuilder(
    transposed=False,    # Whether to transpose the table
    section_by=None,     # Function to group rows into sections
    show_header=True,    # Table options passed to rich.table.Table
)

# Build a table
table = builder(
    data, 
    show_header=False,   # Table options here override constructor options
    show_footer=True,
)

# Or use the convenience class method
table = MyTableBuilder.build(data, show_header=False, show_footer=True)
```

## Development

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/jbchouinard/rich-table-builder.git
cd rich-table-builder

# Install dependencies with Poetry
poetry install
```

### Running Tests

This project uses pytest for testing, including doctests:

```bash
# Run all tests
poetry run pytest
```

### Code Style

This project follows PEP 8 style guidelines and uses ruff for linting and formatting:

```bash
# Run linting
poetry run ruff check .

# Apply automatic fixes
poetry run ruff check --fix .

# Apply formatting
poetry run ruff format .
```

### Commit Conventions

This project follows the [Conventional Commits](https://www.conventionalcommits.org) specification for commit messages. This helps maintain a clear and structured commit history.

Commit message format:
```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

Common types include:
- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code changes that neither fix bugs nor add features
- `test`: Adding or modifying tests
- `chore`: Changes to the build process or auxiliary tools

## License

[MIT License](LICENSE)

Copyright (c) 2025 Jerome Boisvert-Chouinard
