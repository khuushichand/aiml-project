# {{ title }}

> Weekly newsletter briefing — {{ generated_at }}

---

{% for item in items %}
## {{ loop.index }}. {{ item.title }}

{% if item.url %}[Read full article]({{ item.url }}){% endif %}

{{ item.summary or '' }}

{% if item.published_at %}*Published: {{ item.published_at }}*{% endif %}

{% endfor %}

---
*{{ item_count }} items in this edition*
