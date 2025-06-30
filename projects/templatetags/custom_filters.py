from django import template

register = template.Library()

@register.filter(name='filter_by')
def filter_by(queryset, arg):
    """
    Filter a queryset based on a field=value pair.
    
    Usage in template:
    {{ queryset|filter_by:"field=value" }}
    
    Example:
    {{ project.webhooklog_set|filter_by:"file_type=SYNOPSIS" }}
    """
    if not arg or '=' not in arg:
        return queryset.none()
        
    try:
        field, value = arg.split('=', 1)  # Split on first '=' only
        return queryset.filter(**{field.strip(): value.strip()})
    except (ValueError, AttributeError) as e:
        print(f"Error in filter_by: {e}")
        return queryset.none()
