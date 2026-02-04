Implement the following task:
Task: {{task.name}}
Description: {{task.description}}
{% if comments %}
The Pull Request was rejected with the following review comments: 
NOTE: The task description shows the current implementation. 
The comments below indicate ADDITIONAL work that needs to be done.
{% for comment in comments %}
  - {{ comment }}
{% endfor %}
{% if pr_review_message %}
{{ pr_review_message }}
{% endif %}
{% endif %}
{% if plan %}
Complete the task according to the following plan:
{{plan}}
{% endif %}