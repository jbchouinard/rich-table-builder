# Rich Table Builder

A declarative API for building beautiful tables for console output using the [rich](https://github.com/Textualize/rich) library.

## Overview

Rich Table Builder provides a clean, declarative way to define and build tables for console output. It builds on top of `rich.table.Table` and supports all the same arguments while adding powerful features like:

- Declarative table structure definition through class attributes
- Automatic data extraction from objects using flexible key accessors
- Support for transposing tables (rows become columns)
- Automatic aggregation for footers (e.g., column totals)
- Consistent styling for values
- Customizable formatting for cells

## Installation

This project uses Poetry for dependency management. To install:

```bash
# Clone the repository
git clone https://github.com/yourusername/rich-table-builder.git
cd rich-table-builder

# Install dependencies with Poetry
poetry install
```

## Usage

### Basic Example

```python
from rich import print
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
print(table)
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
    **table_options      # Options passed to rich.table.Table
)

# Build a table
table = builder(data, **more_options)

# Or use the convenience class method
table = MyTableBuilder.build(data, **options)
```

## Development

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/yourusername/rich-table-builder.git
cd rich-table-builder

# Install dependencies with Poetry
poetry install
```

### Running Tests

This project uses pytest for testing, including doctests:

```bash
# Run all tests
poetry run pytest

# Run doctests specifically
poetry run pytest richtablebuilder.py -v
```

### Code Style

This project follows PEP 8 style guidelines and uses ruff for linting and formatting:

```bash
# Run linting
poetry run ruff check .

# Apply automatic fixes
poetry run ruff check --fix .
```

## License

[MIT License](LICENSE)