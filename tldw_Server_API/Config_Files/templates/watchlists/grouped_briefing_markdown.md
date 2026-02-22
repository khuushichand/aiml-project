---
name: grouped_briefing_markdown
format: md
description: Grouped briefing with optional LLM summaries
---
# {{ title }}

Generated: {{ generated_at }}
Items: {{ item_count }}{% if has_groups %} | Groups: {{ group_count }}{% endif %}

{% if has_briefing_summary %}
## Executive Summary

{{ briefing_summary }}

---
{% endif %}

{% if has_groups %}
{% for group in groups %}
## {{ group.name }} ({{ group.item_count }} items)

{% if group.summary %}
> {{ group.summary }}

{% endif %}
{% for item in group.items %}
### {{ item.title }}
{{ item.url }}

{% if item.llm_summary is defined and item.llm_summary %}
{{ item.llm_summary }}
{% elif item.summary %}
{{ item.summary }}
{% endif %}

{% if item.published_at %}- Published: {{ item.published_at }}{% endif %}
{% if item.tags %}- Tags: {{ item.tags | join(", ") }}{% endif %}

{% endfor %}
---
{% endfor %}
{% else %}
{% for item in items %}
## {{ item.title }}
{{ item.url }}

{% if item.llm_summary is defined and item.llm_summary %}
{{ item.llm_summary }}
{% elif item.summary %}
{{ item.summary }}
{% endif %}

{% if item.published_at %}- Published: {{ item.published_at }}{% endif %}
{% if item.tags %}- Tags: {{ item.tags | join(", ") }}{% endif %}

---
{% endfor %}
{% endif %}
