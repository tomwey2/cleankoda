# TASK

Test the code.

{% if agent_summary %}

## PREVIOUS NODE SUMMARY

The previous agent completed the following work:

{% for summary in agent_summary %}
- **[{{ summary.role }}]** {{ summary.summary }}
{% endfor %}

{% endif %}