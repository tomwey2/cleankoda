-- 1. Diese Erweiterung aktivieren wir, damit Supabase das 'updated_at' automatisch für uns hochzählt
CREATE EXTENSION IF NOT EXISTS moddatetime;

-- ==========================================
-- Table: public.users
-- This table supplements the system table auth.users with additional user data.
-- ==========================================
CREATE TABLE public.users (
    -- The ID is exactly the same UUID as in the Supabase auth.users table.
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,

    -- Die Brücke zu Stripe
    stripe_customer_id VARCHAR(100),              -- z.B. 'cus_123456789'
    subscription_plan VARCHAR(50) DEFAULT 'FREE', -- Wird per Stripe-Webhook aktualisiert FREE, PRO, TEAM, ENTERPRISE
    is_active BOOLEAN DEFAULT true,

    -- Basis-Profildaten
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    company_name VARCHAR(200),

    -- DSGVO-Nachweise (Consent Tracking)
    accepted_tos_at TIMESTAMPTZ,
    accepted_privacy_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Row Level Security (RLS) aktivieren
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

-- Each user may only view/edit their own profile.
CREATE POLICY "Users can view own profile"
    ON public.users FOR SELECT
    USING (auth.uid() = id);

CREATE POLICY "Users can update own profile"
    ON public.users FOR UPDATE
    USING (auth.uid() = id);

-- A feature that automatically copies new users.
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.users (id)
  VALUES (new.id);
  RETURN new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- The trigger that listens on Supabase
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ==========================================
-- Table: user_credentials
-- ==========================================
CREATE TABLE user_credentials (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,

    -- Typ der Verbindung (z.B. 'GITHUB', 'TRELLO', 'JIRA', 'MISTRAL')
    credential_type VARCHAR(50) NOT NULL,

    -- Ein Name, den der User vergibt (z.B. "Mistral Cloud account" oder "Firmen GitHub")
    name VARCHAR(100) NOT NULL,

    -- E-Mail oder Benutzername. Klartext ist hier völlig in Ordnung,
    -- da diese Information ohne das Passwort nutzlos für Angreifer ist.
    username_or_email VARCHAR(100),

    -- Base URL for the credential (e.g., for Ollama)
    base_url VARCHAR(200),

    -- Hier liegen die verschlüsselten Daten (mit pgcrypto)
    password BYTEA,
    api_key BYTEA,
    api_token BYTEA,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ==========================================
-- Table: agent_settings
-- ==========================================
CREATE TABLE agent_settings (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,

    polling_interval_seconds INTEGER NOT NULL DEFAULT 60,
    is_active BOOLEAN NOT NULL DEFAULT false,
    agent_skill_level VARCHAR(20),
    agent_gender VARCHAR(20),

    -- information about the used issue tracking system
    -- TRELLO, GITHUB ISSUES, JIRA
    its_type VARCHAR(50) NOT NULL,
    its_credential_id INTEGER REFERENCES user_credentials(id),
    its_base_url VARCHAR(200),
    -- Trello: Board-ID | Jira: Project Key (z.B. "ENG") | GitHub: Repo-Name
    its_container_id VARCHAR(100) NOT NULL,
    -- Optional: GitHub braucht zusätzlich den Owner (Org/User), Trello/Jira oft nicht.
    its_parent_id VARCHAR(100),
    its_state_backlog VARCHAR(50),
    its_state_todo VARCHAR(50),
    its_state_in_progress VARCHAR(50),
    its_state_in_review VARCHAR(50),
    its_state_done VARCHAR(50),

    -- information about the used repo system
    repo_type VARCHAR(50) NOT NULL,
    repo_credential_id INTEGER REFERENCES user_credentials(id),
    repo_url VARCHAR(200),

    -- information about the used llm system
    -- MISTRAL, OPENAI, GEMINI
    llm_provider VARCHAR(50) NOT NULL,
    llm_credential_id INTEGER REFERENCES user_credentials(id),
    llm_model_large VARCHAR(100),
    llm_model_small VARCHAR(100),
    llm_temperature VARCHAR(16),

    -- Zeitstempel für Konsistenz ergänzt
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Trigger für automatische Zeitstempel-Updates
CREATE TRIGGER handle_agent_settings_updated_at
    BEFORE UPDATE ON agent_settings
    FOR EACH ROW EXECUTE FUNCTION moddatetime(updated_at);

-- ==========================================
-- Table: agent_tasks
-- ==========================================
CREATE TABLE agent_states (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,

    -- Issue ID from the external issue tracking system
    issue_id VARCHAR(100) NOT NULL UNIQUE,
    -- Issue title and description from the external task system
    issue_name VARCHAR(500) NOT NULL,
    issue_description TEXT,
    -- Issue state ("UNKNOWN", "TODO", "IN_PROGRESS", "IN_REVIEW", "DONE")
    issue_state VARCHAR(20),
    issue_url VARCHAR(200),

    -- Issue type (e.g., "CODING", "ANALYZING", "BUGFIXING")
    issue_type VARCHAR(20),
    -- Task skill level ("JUNIOR", "SENIOR")
    issue_skill_level VARCHAR(20),
    -- The LLM description of the skill level decision
    issue_skill_level_reasoning TEXT,
    issue_is_active BOOLEAN NOT NULL DEFAULT false,

    -- Branch name and repo url of the repository
    repo_branch_name VARCHAR(200),
    repo_pr_url VARCHAR(200),
    repo_pr_number INTEGER,

    -- Content of the implementation plan
    plan_content TEXT,
    -- State of the implementation plan ("CREATED", "UPDATED", "APPROVED", "REJECTED")
    plan_state VARCHAR(20),
    -- Working state of the task ("working...", "finished")
    working_state VARCHAR(20),
    -- User message
    user_message VARCHAR(200),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Den Index für issue_id explizit anlegen (entspricht index=True im Python-Code),
-- um Suchabfragen extrem schnell zu machen.
CREATE INDEX idx_agent_states_issue_id ON agent_states(issue_id);

-- Trigger-Erweiterung sicherstellen (hast du wahrscheinlich schon vom letzten Skript)
CREATE EXTENSION IF NOT EXISTS moddatetime;

-- Trigger für das automatische 'updated_at' erstellen
CREATE TRIGGER handle_agent_states_updated_at
    BEFORE UPDATE ON agent_states
    FOR EACH ROW
    EXECUTE FUNCTION moddatetime(updated_at);

-- ==========================================
-- Table: agent_actions
-- ==========================================
CREATE TABLE agent_actions (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,

    -- WICHTIG: Die Tabelle agent_states muss existieren!
    -- Falls die ID in agent_states ein UUID oder BIGINT ist, musst du INTEGER hier entsprechend anpassen.
    state_id INTEGER REFERENCES agent_states(id) ON DELETE CASCADE,

    node_name VARCHAR(50),
    tool_name VARCHAR(50),
    tool_arg0_name VARCHAR(50),
    tool_arg0_value VARCHAR(200),

    -- TIMESTAMPTZ speichert die Zeit inkl. Zeitzone (Best Practice in Postgres)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Der Trigger, der bei jedem UPDATE die updated_at Spalte auf die aktuelle Zeit setzt
CREATE TRIGGER handle_agent_actions_updated_at
    BEFORE UPDATE ON agent_actions
    FOR EACH ROW
    EXECUTE FUNCTION moddatetime(updated_at);
