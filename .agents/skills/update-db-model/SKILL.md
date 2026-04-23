---
name: update-db-model
description: Helper skill to safely and consistently add, modify, or remove database fields across the entire CleanKoda MVC stack (Database, Schemas, Mappers, Services, and UI).
---

# Update DB Model Skill

When the user asks you to add, modify, or remove a database field/column for a specific model, it is critical to ensure consistency across the entire application architecture. Follow this step-by-step checklist to implement the change fully.

## Implementation Checklist

Whenever making model changes, you MUST verify and update the following layers in order:

### 1. Database Model (`src/core/localdb/models.py`)
- Locate the correct SQLAlchemy model class.
- Add/Update the column definition (e.g., `db.Column(db.String, nullable=True)`).
- Ensure safe default values exist if you are adding a column to an existing table to avoid breaking older databases.

### 2. Validation & Schemas (`src/web/schemas/`)
- Find the corresponding Pydantic validation schema or input form schema.
- Add the new field with appropriate type hints and default values (e.g., `Optional[str] = None`).
- Ensure the `description` parameter is set on `Field()` if the LLM or UI requires context.

### 3. Mapper Logic (`src/web/mappers/`)
- Mappers handle the translation between Database Models and API/Form Schemas.
- Find the mapping functions (e.g., in `settings_mapper.py`).
- Ensure the new field is passed cleanly from the DB model into the Schema instance, and vice versa.

### 4. Business Logic (`src/web/services/`)
- Update any business service (e.g., `settings_service.py` or `dashboard_service.py`) that reads, writes, or provides template contexts involving the updated model.
- Handle potential `None` or missing values safely (e.g., using `getattr` or inline `.get()` operations) to preserve backward compatibility.

### 5. Frontend & UI (`src/web/templates/`)
- If this field is visible to the user, locate the corresponding HTML/Jinja template (e.g., `settings.html` or `credentials_form.html`).
- Add the necessary UI elements (input fields, labels, or display rows).
- Ensure styling matches the existing CSS classes in the project.

## How to execute
When invoked, you MUST:
1. Search the repository for all files that reference the modified model name.
2. Edit each file systematically according to the checklist above.
3. Present the user with a short summary of all components touched to guarantee nothing was missed.
