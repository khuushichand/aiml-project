# {{ title }} — Categorized Briefing

*Generated at {{ generated_at }}*

{% set ns = namespace(categorized={}) %}
{% for item in items %}
{% set cat = (item.tags[0] if item.tags else 'Uncategorized') %}
{% if cat not in ns.categorized %}{% set _ = ns.categorized.update({cat: []}) %}{% endif %}
{% set _ = ns.categorized[cat].append(item) %}
{% endfor %}

{% for category, cat_items in ns.categorized.items() %}
## {{ category }}

{% for item in cat_items %}
- {% if item.url %}[{{ item.title }}]({{ item.url }}){% else %}{{ item.title }}{% endif %}{% if item.summary %}: {{ item.summary[:200] }}{% endif %}

{% endfor %}
{% endfor %}

---
*{{ item_count }} items across {{ ns.categorized | length }} categories*
