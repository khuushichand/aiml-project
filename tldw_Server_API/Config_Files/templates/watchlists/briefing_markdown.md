# {{ title }}

*Generated at {{ generated_at }}*

{% if items %}
{% for item in items %}
{{ loop.index }}. {% if item.url %}[{{ item.title }}]({{ item.url }}){% else %}{{ item.title }}{% endif %}

{% if item.summary %}   {{ item.summary[:300] }}{% endif %}

{% if item.tags %}   Tags: {{ item.tags | join(', ') }}{% endif %}

{% endfor %}
{% else %}
*No items available.*
{% endif %}

---
*{{ item_count }} items total*
