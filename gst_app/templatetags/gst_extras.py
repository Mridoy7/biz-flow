from django import template
from django.forms import FileInput

register = template.Library()


@register.filter
def currency(value):
    if value in (None, ""):
        value = 0
    return f"${value:,.2f}"


@register.filter
def add_class(field, css_class):
    existing = field.field.widget.attrs.get("class", "")
    classes = f"{existing} {css_class}".strip()
    return field.as_widget(attrs={"class": classes})


@register.filter
def add_attrs(field, attrs):
    widget_attrs = {}
    for item in attrs.split(","):
        if ":" not in item:
            continue
        key, value = item.split(":", 1)
        widget_attrs[key.strip()] = value.strip()
    return field.as_widget(attrs=widget_attrs)


@register.filter
def is_file_field(field):
    return isinstance(field.field.widget, FileInput)


@register.filter
def is_fuel_dip_field(field):
    return field.name.startswith("fuel_dip_")


@register.filter
def basename(value):
    if not value:
        return ""
    return str(value).rsplit("/", 1)[-1]
