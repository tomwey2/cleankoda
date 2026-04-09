# ISSUE

Analyze the following issue:
Issue: {{agent_issue.issue_name}}
Description: {{agent_issue.issue_description}}

{% if agent_summary %}

## PREVIOUS NODE SUMMARY

The previous agent completed the following work:

{% for summary in agent_summary %}
- **[{{ summary.role }}]** {{ summary.summary }}
{% endfor %}

{% endif %}
{% if issue_comments %}
# REVIEW COMMENTS
The Pull Request was rejected with the following review comments: 
NOTE: The issue description shows the current implementation. 
The comments below indicate ADDITIONAL work that needs to be done.
{% for comment in issue_comments %}
  - {{ comment.text }}
{% endfor %}
{% endif %}
{% if pr_review_message %}
# PULL REQUEST MESSAGE
{{ pr_review_message }}
{% endif %}
{% if agent_issue.plan_content %}
# SPECIFIC IMPLEMENTATION PLAN
You MUST follow these exact steps to complete the issue:
{{agent_issue.plan_content}}
{% endif %}