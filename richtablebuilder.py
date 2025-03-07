"""
tablebuilder is a declarative API for building rich tables for console output.
It uses rich.table.Table under the hood and supports all the same arguments.

The structure of a table is defined by subclassing TableBuilder.
The columns are defined by TableField attributes.
(If the table is transposed, each field corresponds to a row instead.)

>>> import rich
>>> from richtablebuilder import TableBuilder, TableField, Obj
>>>
>>> def subtotal(item, _):
...     return item["quantity"] * item["price"]
>>>
>>> class CartTableBuilder(TableBuilder):
...     name = TableField("Item Name", key="name", footer="Total")
...     quantity = TableField("Quantity", key="quantity", footer=sum)
...     price = TableField("Item Price", key="price", footer="-")
...     subtotal = TableField("Subtotal", key=subtotal, footer=sum)
>>>
>>> my_table_builder = CartTableBuilder(show_header=True, show_footer=True)
>>> cart = [
...     {"name": "Item 1", "quantity": 1, "price": 10},
...     {"name": "Item 2", "quantity": 2, "price": 20},
... ]
>>> table = my_table_builder(cart, title="Some Cart")
>>> rich.print(table)  # doctest: +SKIP
>>> # pass transposed=True to print the table row-based
>>> table_t = my_table_builder(cart, title="Some Cart", transposed=True)
>>> rich.print(table_t)  # doctest: +SKIP

TableBuilder does not contain the table data; it is applied
to a list of data objects to produce the table.

The key argument to TableField determines how the value for each field
is retrieved from data objects. It can be a two-parameter function
(accepting the data object and a default value), or a string,
in which case it is used for dictionary lookup.

`Obj` can be used to define key functions for nested attributes or dictionary keys,
for example `Obj.cart.items["price"]` is a function that is roughly equivalent to

    lambda obj: obj.cart.items["price"]

except that `Obj` accepts an optional default value.

Any keyword arguments supported by `rich.table.Table` can be passed
when constructing a `TableBuilder`, or when building a table
(which overrides the values passed to the constructor).

TableBuilder is not just syntactic sugar, it adds some extra features
on top of `rich.table.Table`.

The main additional features are support for transposing tables,
and the ability to pass functions as header or footer to TableField,
which are automatically applied by TableBuilder.
For example, footer=sum is passed to produce a column total.
"""

import typing
from collections.abc import Iterable
from typing import Any, Callable, NamedTuple, TypedDict, final

if typing.TYPE_CHECKING:
    from _typeshed import SupportsRichComparison
else:
    SupportsRichComparison = object  # pyright: ignore[reportUnreachable]

from rich import box
from rich.console import JustifyMethod, RenderableType
from rich.padding import PaddingDimensions
from rich.style import StyleType
from rich.styled import Styled
from rich.table import Column, Table
from rich.text import Text
from typing_extensions import NotRequired, Unpack, override

Getter = Callable[[Any, Any], Any]
Formatter = Callable[[Any], RenderableType]
Reducer = Callable[[list[Any]], Any]
SortBy = Callable[[Any], SupportsRichComparison]


NO_DEFAULT = object()
MISSING = object()


@final
class ObjType:
    """
    ObjType is used to declaratively create getters for nested fields or attributes on objects.

    Normally it is not instantiated, the existing Obj instance should be used instead.

    Example:
    >>> getter = Obj["a"]["b"]
    >>> getter({"a": {"b": 1}})
    1
    >>> getter = Obj.a.b
    >>> getter("foo")
    Traceback (most recent call last):
    ...
    KeyError: 'Obj.a.b'
    >>> getter("foo", "default")
    'default'
    >>> # Obj itself acts as the identity function
    >>> Obj(12)
    12
    >>> Obj[1](("foo", "bar"))
    'bar'
    """

    @override
    def __init__(
        self,
        accessors: Iterable[tuple[str, str | int]],
        transforms: Iterable[Callable[[Any], Any]] | None = None,
    ):
        self.__accessors__ = tuple(accessors)
        self.__transforms__ = tuple(transforms or ())

    def _apply(self, f: Callable[[Any], Any]) -> "ObjType":  # pyright: ignore[reportUnusedFunction]
        return ObjType(self.__accessors__, self.__transforms__ + (f,))

    def __call__(self, obj: Any, default: Any = NO_DEFAULT) -> Any:
        for t, k in self.__accessors__:
            if t == "key":
                try:
                    obj = obj[k]
                except (KeyError, IndexError):
                    obj = MISSING
            else:
                assert isinstance(k, str)
                obj = getattr(obj, k, MISSING)
            if obj is MISSING:
                if default is NO_DEFAULT:
                    raise KeyError(f"{repr(self)}")
                else:
                    obj = default

        for transform in self.__transforms__:
            obj = transform(obj)
        return obj

    @override
    def __repr__(self):
        parts = ["Obj"]
        for t, k in self.__accessors__:
            if t == "key":
                parts.append(f"[{repr(k)}]")
            else:
                parts.append(f".{k}")
        return "".join(parts)

    def __getitem__(self, k: str | int):
        return ObjType(self.__accessors__ + (("key", k),))

    def __getattr__(self, k: str):
        return ObjType(self.__accessors__ + (("attr", k),))


Obj = ObjType(())


@final
class TableField:
    def __init__(
        self,
        header: RenderableType | Reducer = "",
        footer: RenderableType | Reducer = "",
        key: ObjType | Getter | str | None = None,
        default: Any = None,
        formatter: Formatter | None = str,
        style: StyleType = "",
        header_style: StyleType = "",
        footer_style: StyleType = "",
        justify: JustifyMethod = "left",
    ):
        """
        Initialize a TableField with the specified parameters.

        Args:
            header: The header text or a reducer function to generate the header
            footer: The footer text or a reducer function to generate the footer
            key: How to extract values from data objects (string key, callable, or Obj expression)
            default: Default value to use when key is not found
            formatter: Function to format field values
            style: Style to apply to field values
            header_style: Style to apply to the header
            footer_style: Style to apply to the footer
            justify: Text justification ("left", "center", "right")

        Example:
            >>> from richtablebuilder import TableField, Obj
            >>> # Simple string key
            >>> field = TableField("Name", key="name")
            >>> field._get_field_value({"name": "Alice"})
            'Alice'
            >>> # Using Obj for nested access
            >>> field = TableField("Address", key=Obj["contact"]["address"])
            >>> field._get_field_value({"contact": {"address": "123 Main St"}})
            '123 Main St'
            >>> # Using a formatter
            >>> field = TableField("Price", key="price", formatter=lambda x: f"${x:.2f}")
            >>> field._format_field_value(10.5)
            '$10.50'
        """
        self.header = header
        self.name: str | None = None
        if key is None:
            self.getter = Obj
        elif callable(key):
            self.getter = key
        elif isinstance(key, str):
            self.getter = Obj[key]
        else:
            raise TypeError(f"Invalid key type: {type(key)}")  # pyright: ignore[reportUnreachable]

        self.default = default
        self.formatter = formatter
        self.footer = footer
        self.style = style
        self.header_style = header_style
        self.footer_style = footer_style
        self.justify: JustifyMethod = justify

    def column(self, header: RenderableType, footer: RenderableType = "") -> Column:
        """
        Create a rich.table.Column from this TableField.

        Returns:
            A rich.table.Column object configured with this field's properties

        Example:
            >>> from richtablebuilder import TableField
            >>> field = TableField("Name", justify="center", style="bold")
            >>> column = field.column("Name")
            >>> column.header
            'Name'
            >>> column.justify
            'center'
            >>> column.style
            'bold'
        """
        return Column(
            header,
            footer=footer,
            justify=self.justify,
            style=self.style,
            header_style=self.header_style,
            footer_style=self.footer_style,
        )

    def _apply_style(self, val: Any, style: StyleType = "") -> RenderableType:
        if isinstance(val, str):
            styled_val = Text(val, style=style)
        else:
            styled_val = Styled(val, style=style)
        return styled_val

    def _get_field_value(self, obj: Any) -> Any:
        val = self.getter(obj, self.default)
        if val is None:
            val = self.default
        return val

    def _format_field_value(
        self, val: Any, apply_style: bool = False, default_style: StyleType = ""
    ) -> RenderableType:
        if val is None:
            val = ""
        if self.formatter and val is not None:
            val = self.formatter(val)
        if apply_style:
            val = self._apply_style(val, self.style or default_style)
        return val

    def _reduce_and_format(
        self,
        rx: Reducer | RenderableType,
        values: list[Any],
    ) -> RenderableType:
        if callable(rx):
            value = rx(values)
            if self.formatter and value is not None:
                value = self.formatter(value)
        else:
            value = rx

        return value

    def _get_header(
        self,
        values: list[Any],
        apply_style: bool = False,
        default_style: StyleType = "",
    ) -> RenderableType:
        value = self._reduce_and_format(self.header, values)
        if apply_style:
            value = self._apply_style(value, self.header_style or default_style)

        return value

    def _get_footer(
        self,
        values: list[Any],
        apply_style: bool = False,
        default_style: StyleType = "",
    ) -> RenderableType:
        value = self._reduce_and_format(self.footer, values)
        if apply_style:
            value = self._apply_style(value, self.footer_style or default_style)
        return value


class TableFieldContent(NamedTuple):
    header: RenderableType
    values: list[RenderableType]
    footer: RenderableType


class TableOptions(TypedDict):
    title: NotRequired[str | Text]
    caption: NotRequired[str | Text]
    width: NotRequired[int]
    min_width: NotRequired[int]
    box: NotRequired[box.Box]
    safe_box: NotRequired[bool]
    padding: NotRequired[PaddingDimensions]
    collapse_padding: NotRequired[bool]
    pad_edge: NotRequired[bool]
    expand: NotRequired[bool]
    show_header: NotRequired[bool]
    show_footer: NotRequired[bool]
    show_edge: NotRequired[bool]
    show_lines: NotRequired[bool]
    leading: NotRequired[int]
    style: NotRequired[StyleType]
    row_styles: NotRequired[Iterable[StyleType]]
    header_style: NotRequired[StyleType]
    footer_style: NotRequired[StyleType]
    border_style: NotRequired[StyleType]
    title_style: NotRequired[StyleType]
    caption_style: NotRequired[StyleType]
    title_justify: NotRequired[JustifyMethod]
    caption_justify: NotRequired[JustifyMethod]
    highlight: NotRequired[bool]


@final
class TableBuilderMeta(type):
    @override
    def __init__(cls, name: str, bases: tuple[type, ...], attrs: dict[str, Any]):
        cls._table_fields: dict[str, TableField] = {
            attr: v for attr, v in attrs.items() if isinstance(v, TableField)
        }
        for attr, column in cls._table_fields.items():
            if column.name is None:
                column.name = attr
        super().__init__(name, bases, attrs)


class TableBuilder(metaclass=TableBuilderMeta):
    def __init__(
        self,
        transposed: bool = False,
        section_by: SortBy | None = None,
        **kwargs: Unpack[TableOptions],
    ):
        self.transposed: bool = transposed
        self.section_by: SortBy | None = section_by
        self.default_table_kwargs: TableOptions = {
            "show_header": kwargs.get("show_header", True),
            "show_footer": kwargs.get("show_footer", False),
            "style": kwargs.get("style", "none"),
            "header_style": kwargs.get("header_style", "table.header"),
            "footer_style": kwargs.get("footer_style", "table.footer"),
        }
        for opt, val in kwargs.items():
            self.default_table_kwargs[opt] = val

    def __call__(
        self,
        data: Iterable[Any],
        transposed: bool = False,
        **kwargs: Unpack[TableOptions],
    ) -> Table:
        """
        Build a rich.table.Table from the provided data.

        Args:
            data: Iterable of data objects to build the table from
            transposed: Whether to transpose the table (rows become columns)
            **kwargs: Additional options to pass to rich.table.Table

        Returns:
            A rich.table.Table instance

        Example:
            >>> from richtablebuilder import TableBuilder, TableField
            >>> class SimpleTableBuilder(TableBuilder):
            ...     name = TableField("Name", key="name")
            ...     value = TableField("Value", key="value")
            >>> data = [{"name": "Alice", "value": 42}, {"name": "Bob", "value": 24}]
            >>> builder = SimpleTableBuilder()
            >>> table = builder(data)
            >>> len(table.columns)
            2
            >>> # Check that the table has two rows (plus header)
            >>> len(table.rows)
            2
        """
        table_kwargs = self.default_table_kwargs.copy()
        for opt, val in kwargs.items():
            table_kwargs[opt] = val
        return self._build_table(data, table_kwargs, transposed=transposed)

    @classmethod
    def build(
        cls,
        data: list[Any],
        transposed: bool = False,
        section_by: SortBy | None = None,
        **kwargs: Unpack[TableOptions],
    ) -> Table:
        """
        Build a table directly from data without creating a TableBuilder instance first.

        This is a convenience method that creates a TableBuilder instance and immediately
        applies it to the data.

        Args:
            data: List of data objects to build the table from
            transposed: Whether to transpose the table (rows become columns)
            **kwargs: Additional options to pass to rich.table.Table

        Returns:
            A rich.table.Table instance

        Example:
            >>> from richtablebuilder import TableBuilder, TableField
            >>> class SimpleTableBuilder(TableBuilder):
            ...     name = TableField("Name", key="name")
            ...     value = TableField("Value", key="value")
            >>> data = [{"name": "Alice", "value": 42}, {"name": "Bob", "value": 24}]
            >>> table = SimpleTableBuilder.build(data, title="Simple Table")
            >>> table.title
            'Simple Table'
            >>> len(table.columns)
            2
        """
        return cls(transposed=transposed, section_by=section_by, **kwargs)(data)

    def _build_field_content(
        self,
        tf: TableField,
        items: list[Any],
        table_kwargs: TableOptions,
        apply_style: bool = False,
    ) -> TableFieldContent:
        values = [tf._get_field_value(item) for item in items]
        header = tf._get_header(
            values,
            apply_style=apply_style,
            default_style=table_kwargs.get("header_style", ""),
        )
        footer = tf._get_footer(
            values,
            apply_style=apply_style,
            default_style=table_kwargs.get("footer_style", ""),
        )
        values = [
            tf._format_field_value(
                v,
                apply_style=apply_style,
                default_style=table_kwargs.get("style", ""),
            )
            for v in values
        ]
        return TableFieldContent(header, values, footer)

    def _build_table(
        self, items: Iterable[Any], table_kwargs: TableOptions, transposed: bool | None = False
    ) -> Table:
        if transposed is None:
            transposed = self.transposed

        items = list(items)
        if transposed:
            return self._build_table_transposed(items, table_kwargs)
        else:
            return self._build_table_normal(items, table_kwargs)

    def _build_table_normal(self, items: list[Any], table_kwargs: TableOptions) -> Table:
        if self.section_by is not None:
            items = sorted(items, key=self.section_by)
            section_markers = [self.section_by(item) for item in items]
        else:
            section_markers = [True] * len(items)

        columns: list[Column] = []
        rows: list[list[RenderableType]] = [[] for _ in range(len(items))]
        for tf in self._table_fields.values():
            column_content = self._build_field_content(tf, items, table_kwargs)
            columns.append(
                tf.column(header=column_content.header, footer=column_content.footer or "")
            )
            for row_idx, val in enumerate(column_content.values):
                rows[row_idx].append(val)

        table = Table(*columns, **table_kwargs)
        if rows:
            current_marker = section_markers[0]
            for marker, row in zip(section_markers, rows, strict=False):
                if marker != current_marker:
                    table.add_section()
                    current_marker = marker
                table.add_row(*row)
        return table

    def _build_table_transposed(self, values: list[Any], table_kwargs: TableOptions) -> Table:
        # The header and footer on a transposed table are the first and last value of each row.
        # We must build it ourselves, so force them to False to rich.Table
        show_header = table_kwargs.pop("show_header", True)
        show_footer = table_kwargs.pop("show_footer", False)
        table_kwargs["show_header"] = False
        table_kwargs["show_footer"] = False

        column_count = len(values) + show_header + show_footer
        columns = [Column(f"row{n}") for n in range(column_count)]
        rows: list[list[RenderableType]] = []
        for tf in self._table_fields.values():
            row: list[RenderableType] = []
            row_content = self._build_field_content(tf, values, table_kwargs, apply_style=True)
            if show_header:
                row.append(row_content.header or "")
            row.extend(row_content.values)
            if show_footer:
                row.append(row_content.footer or "")
            rows.append(row)

        table = Table(*columns, **table_kwargs)
        for row in rows:
            table.add_row(*row)
        return table


RAINBOW_COLORS: list[str] = [
    "red",
    "orange1",
    "yellow2",
    "green3",
    "cyan1",
    "deep_sky_blue1",
    "dark_blue",
    "dark_violet",
]


_rainbow_idx: int = 0


def rainbow_cycle() -> StyleType:
    """
    Generate colors in a rainbow sequence, cycling through predefined colors.

    Each call returns the next color in the sequence, cycling back to the beginning
    after reaching the end of the color list.

    Returns:
        A color name from the RAINBOW_COLORS list

    Example:
        >>> from richtablebuilder import rainbow_cycle
        >>> # Get the first color
        >>> first_color = rainbow_cycle()
        >>> first_color in RAINBOW_COLORS
        True
        >>> # Get the next color
        >>> second_color = rainbow_cycle()
        >>> second_color in RAINBOW_COLORS
        True
        >>> # Colors should be different in sequence
        >>> first_color != second_color
        True
    """
    global _rainbow_idx
    color = RAINBOW_COLORS[_rainbow_idx]
    _rainbow_idx = (_rainbow_idx + 1) % len(RAINBOW_COLORS)
    return color


def style_by_value(next_style: Callable[[], StyleType]) -> Callable[[RenderableType], Styled]:
    """
    Create a formatter function that applies consistent styles to values.

    This function creates a closure that remembers which style was applied to each
    unique value, ensuring that the same value always gets the same style.

    Args:
        next_style: A function that returns the next style to use

    Returns:
        A formatter function that applies styles consistently to values

    Example:
        >>> from richtablebuilder import style_by_value
        >>> # Create a simple style generator
        >>> styles = ["red", "blue", "green"]
        >>> style_idx = 0
        >>> def next_color():
        ...     global style_idx
        ...     color = styles[style_idx]
        ...     style_idx = (style_idx + 1) % len(styles)
        ...     return color
        >>> formatter = style_by_value(next_color)
        >>> # Same values get the same style
        >>> styled1 = formatter("apple")
        >>> styled2 = formatter("banana")
        >>> styled3 = formatter("apple")
        >>> styled1.style == styled3.style  # Same value gets same style
        True
        >>> styled1.style != styled2.style  # Different values get different styles
        True
    """
    seen_values: dict[Any, StyleType] = {}

    def format_value(value: RenderableType) -> Styled:
        nonlocal seen_values
        if value not in seen_values:
            seen_values[value] = next_style()
        style = seen_values[value]
        return Styled(value, style=style)

    return format_value


rainbow_by_value = style_by_value(rainbow_cycle)


def example():
    import rich

    class Item(TypedDict):
        name: str
        price: float
        quantity: int

    def compute_subtotal(item: Item, _: float) -> float:
        """
        Calculate the subtotal for an item by multiplying quantity by price.
        """
        return item["quantity"] * item["price"]

    def format_currency(value: float) -> RenderableType:
        """
        Format a numeric value as currency with dollar sign.
        """
        if value >= 0.0:
            return f"${value:.2f}"
        else:
            return Text(f"(${-value:.2f})", style="red")

    @final
    class CartTableBuilder(TableBuilder):
        name = TableField(
            "Item Name",
            key="name",
            footer="Total",
            justify="left",
            style="bold",
            formatter=rainbow_by_value,
        )
        price = TableField(
            "Price",
            key="price",
            footer="-",
            formatter=format_currency,
            justify="right",
        )
        quantity = TableField(
            "Quantity",
            key="quantity",
            footer=sum,
            justify="right",
        )
        subtotal = TableField(
            "Subtotal",
            key=compute_subtotal,
            footer=sum,
            formatter=format_currency,
            justify="right",
        )

    my_table_builder = CartTableBuilder(show_header=True, show_footer=True, box=box.HORIZONTALS)
    cart = [
        {"name": "Item 1", "quantity": 1, "price": 10},
        {"name": "Item 2", "quantity": 2, "price": 20},
        {"name": "Item 3", "quantity": 3, "price": 30},
        {"name": "Item 4", "quantity": 4, "price": 40},
        {"name": "Item 5", "quantity": 5, "price": 50},
        {"name": "Item 5", "quantity": 6, "price": 60},
        {"name": "Item 6", "quantity": 7, "price": 70},
        {"name": "Item 7", "quantity": 8, "price": 80},
        {"name": "Discount", "quantity": 1, "price": -10},
    ]
    table = my_table_builder(cart, title=Text("Some Cart"))
    rich.print(table)
    print()
    table_t = my_table_builder(
        cart,
        title="Some Cart - Transposed",
        transposed=True,
        box=box.SIMPLE,
        show_lines=False,
    )
    rich.print(table_t)


if __name__ == "__main__":
    example()
