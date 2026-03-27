## Database & Multi-tenancy (Supabase)

To guarantee a stateless architecture, Supabase (serverless PostgreSQL) completely replaces local databases.

### Key Features

**1. Auth & Identity:** Supabase manages the login system (JWT tokens) securely and scalably: Supabase handles the entire login system (e.g., "Sign in with GitHub" or "Sign in with Google"). Flask does not need to store passwords. We use Supabase's secure JWT tokens (JSON Web Tokens) to manage user sessions in the dashboard.

**2. Multi-tenancy (RLS):** Each table is assigned a tenant_id. Supabase's "Row Level Security" (RLS) ensures at the database level that a user may only read or edit rows where the tenant_id matches their own user ID. Even in the event of a bug in our Flask backend, Customer A can never see Customer B's data.

**3. Operations Dashboard:** The Supabase Studio web interface serves as a direct admin panel. CleanKoda does not require its own admin panel. The Supabase Studio (web interface) acts as a control center: Here you can immediately see new registrations, active agent jobs, connected repositories, and, in the case of support requests, directly view the logs (agent_logs table) of a specific job.

### Datamodel

#### Multi-tenancy

### Authentication



