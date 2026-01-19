# {{ title }}

Generated at: {{ generated_at }}

## Digest items
{% for item in items %}
- [{{ item.title }}]({{ item.url }}){% if item.summary %} - {{ item.summary }}{% endif %}
{% endfor %}

{% if suggestions %}
## Suggested reads
{% for item in suggestions %}
- [{{ item.title }}]({{ item.url }}){% if item.summary %} - {{ item.summary }}{% endif %}
{% endfor %}
{% endif %}
