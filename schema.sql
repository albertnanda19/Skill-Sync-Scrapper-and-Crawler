-- DROP SCHEMA public;

CREATE SCHEMA public AUTHORIZATION pg_database_owner;

COMMENT ON SCHEMA public IS 'standard public schema';
-- public.job_sources definition

-- Drop table

-- DROP TABLE public.job_sources;

CREATE TABLE public.job_sources ( id uuid NOT NULL, "name" text NULL, base_url text NULL, created_at timestamptz DEFAULT now() NULL, CONSTRAINT job_sources_name_key UNIQUE (name), CONSTRAINT job_sources_pkey PRIMARY KEY (id));
COMMENT ON TABLE public.job_sources IS 'Job listing sources used by the scraper.';

-- Permissions

ALTER TABLE public.job_sources OWNER TO postgres;
GRANT ALL ON TABLE public.job_sources TO postgres;


-- public.schema_migrations definition

-- Drop table

-- DROP TABLE public.schema_migrations;

CREATE TABLE public.schema_migrations ( "version" int8 NOT NULL, "name" text NOT NULL, checksum text NOT NULL, applied_at timestamptz DEFAULT now() NOT NULL, CONSTRAINT schema_migrations_pkey PRIMARY KEY (version));

-- Permissions

ALTER TABLE public.schema_migrations OWNER TO postgres;
GRANT ALL ON TABLE public.schema_migrations TO postgres;


-- public.scrape_tasks definition

-- Drop table

-- DROP TABLE public.scrape_tasks;

CREATE TABLE public.scrape_tasks ( id uuid NOT NULL, query varchar NOT NULL, "location" varchar NOT NULL, status varchar NOT NULL, total_found int4 NULL, created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL, error_message text NULL, CONSTRAINT uq_scrape_tasks_id PRIMARY KEY (id));

-- Permissions

ALTER TABLE public.scrape_tasks OWNER TO postgres;
GRANT ALL ON TABLE public.scrape_tasks TO postgres;


-- public.skills definition

-- Drop table

-- DROP TABLE public.skills;

CREATE TABLE public.skills ( id uuid NOT NULL, "name" text NOT NULL, category text NULL, created_at timestamptz DEFAULT now() NULL, CONSTRAINT skills_name_key UNIQUE (name), CONSTRAINT skills_pkey PRIMARY KEY (id));
COMMENT ON TABLE public.skills IS 'Normalized skill taxonomy.';

-- Permissions

ALTER TABLE public.skills OWNER TO postgres;
GRANT ALL ON TABLE public.skills TO postgres;


-- public.users definition

-- Drop table

-- DROP TABLE public.users;

CREATE TABLE public.users ( id uuid NOT NULL, email text NOT NULL, password_hash text NOT NULL, created_at timestamptz DEFAULT now() NULL, updated_at timestamptz DEFAULT now() NULL, CONSTRAINT users_email_key UNIQUE (email), CONSTRAINT users_pkey PRIMARY KEY (id));
COMMENT ON TABLE public.users IS 'Authentication and core user identity records.';

-- Permissions

ALTER TABLE public.users OWNER TO postgres;
GRANT ALL ON TABLE public.users TO postgres;


-- public.jobs definition

-- Drop table

-- DROP TABLE public.jobs;

CREATE TABLE public.jobs ( id uuid NOT NULL, source_id uuid NULL, external_job_id text NULL, title text NULL, company text NULL, "location" text NULL, employment_type text NULL, description text NULL, raw_description text NULL, posted_at timestamptz NULL, scraped_at timestamptz NULL, created_at timestamptz DEFAULT now() NULL, url text NULL, is_active bool DEFAULT true NOT NULL, "source" text DEFAULT 'unknown'::text NULL, source_url text NULL, CONSTRAINT jobs_pkey PRIMARY KEY (id), CONSTRAINT jobs_source_id_external_job_id_key UNIQUE (source_id, external_job_id), CONSTRAINT jobs_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.job_sources(id));
CREATE INDEX idx_jobs_source_id_scraped_at ON public.jobs USING btree (source_id, scraped_at);
CREATE UNIQUE INDEX idx_jobs_source_id_url_unique ON public.jobs USING btree (source_id, url);
CREATE INDEX idx_jobs_source_url ON public.jobs USING btree (source_url);
COMMENT ON TABLE public.jobs IS 'Scraped job postings (deduplicated per source + external id).';

-- Permissions

ALTER TABLE public.jobs OWNER TO postgres;
GRANT ALL ON TABLE public.jobs TO postgres;


-- public.scrape_runs definition

-- Drop table

-- DROP TABLE public.scrape_runs;

CREATE TABLE public.scrape_runs ( id uuid NOT NULL, source_id uuid NULL, started_at timestamptz NULL, finished_at timestamptz NULL, status text NULL, CONSTRAINT scrape_runs_pkey PRIMARY KEY (id), CONSTRAINT scrape_runs_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.job_sources(id));
COMMENT ON TABLE public.scrape_runs IS 'Scraping execution runs per source.';

-- Permissions

ALTER TABLE public.scrape_runs OWNER TO postgres;
GRANT ALL ON TABLE public.scrape_runs TO postgres;


-- public.user_profiles definition

-- Drop table

-- DROP TABLE public.user_profiles;

CREATE TABLE public.user_profiles ( id uuid NOT NULL, user_id uuid NULL, experience_level text NULL, preferred_roles _text NULL, created_at timestamptz DEFAULT now() NULL, updated_at timestamptz DEFAULT now() NULL, full_name text NULL, CONSTRAINT user_profiles_pkey PRIMARY KEY (id), CONSTRAINT user_profiles_user_id_key UNIQUE (user_id), CONSTRAINT user_profiles_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id));
COMMENT ON TABLE public.user_profiles IS 'Extended user profile attributes (1:1 with users).';

-- Permissions

ALTER TABLE public.user_profiles OWNER TO postgres;
GRANT ALL ON TABLE public.user_profiles TO postgres;


-- public.user_skills definition

-- Drop table

-- DROP TABLE public.user_skills;

CREATE TABLE public.user_skills ( id uuid NOT NULL, user_id uuid NULL, skill_id uuid NULL, proficiency_level int2 NULL, created_at timestamptz DEFAULT now() NULL, years_experience int2 NULL, CONSTRAINT user_skills_pkey PRIMARY KEY (id), CONSTRAINT user_skills_user_id_skill_id_key UNIQUE (user_id, skill_id), CONSTRAINT user_skills_skill_id_fkey FOREIGN KEY (skill_id) REFERENCES public.skills(id), CONSTRAINT user_skills_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id));
COMMENT ON TABLE public.user_skills IS 'User-to-skill mapping with proficiency.';

-- Permissions

ALTER TABLE public.user_skills OWNER TO postgres;
GRANT ALL ON TABLE public.user_skills TO postgres;


-- public.job_matches definition

-- Drop table

-- DROP TABLE public.job_matches;

CREATE TABLE public.job_matches ( id uuid NOT NULL, user_id uuid NULL, job_id uuid NULL, match_score numeric(5, 2) NULL, matched_at timestamptz NULL, CONSTRAINT job_matches_pkey PRIMARY KEY (id), CONSTRAINT job_matches_user_id_job_id_key UNIQUE (user_id, job_id), CONSTRAINT job_matches_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.jobs(id), CONSTRAINT job_matches_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id));
COMMENT ON TABLE public.job_matches IS 'Computed match score between users and jobs.';

-- Permissions

ALTER TABLE public.job_matches OWNER TO postgres;
GRANT ALL ON TABLE public.job_matches TO postgres;


-- public.job_skills definition

-- Drop table

-- DROP TABLE public.job_skills;

CREATE TABLE public.job_skills ( id uuid NOT NULL, job_id uuid NULL, skill_id uuid NULL, importance_weight int2 NULL, required_level int4 NULL, is_mandatory bool NULL, required_years int4 NULL, source_version int2 DEFAULT 1 NOT NULL, CONSTRAINT job_skills_importance_weight_check CHECK (((importance_weight IS NULL) OR ((importance_weight >= 1) AND (importance_weight <= 5)))), CONSTRAINT job_skills_job_id_skill_id_key UNIQUE (job_id, skill_id), CONSTRAINT job_skills_pkey PRIMARY KEY (id), CONSTRAINT job_skills_required_level_check CHECK (((required_level IS NULL) OR ((required_level >= 1) AND (required_level <= 5)))), CONSTRAINT job_skills_required_years_check CHECK (((required_years IS NULL) OR (required_years >= 0))), CONSTRAINT job_skills_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.jobs(id), CONSTRAINT job_skills_skill_id_fkey FOREIGN KEY (skill_id) REFERENCES public.skills(id));
CREATE INDEX idx_job_skills_job_id ON public.job_skills USING btree (job_id);
CREATE INDEX idx_job_skills_job_id_is_mandatory ON public.job_skills USING btree (job_id, is_mandatory);
CREATE UNIQUE INDEX idx_job_skills_job_id_skill_id ON public.job_skills USING btree (job_id, skill_id);
CREATE INDEX idx_job_skills_skill_id ON public.job_skills USING btree (skill_id);
COMMENT ON TABLE public.job_skills IS 'Skill requirements inferred/extracted for jobs.';

-- Permissions

ALTER TABLE public.job_skills OWNER TO postgres;
GRANT ALL ON TABLE public.job_skills TO postgres;


-- public.scrape_logs definition

-- Drop table

-- DROP TABLE public.scrape_logs;

CREATE TABLE public.scrape_logs ( id uuid NOT NULL, scrape_run_id uuid NULL, "level" text NULL, message text NULL, created_at timestamptz DEFAULT now() NULL, CONSTRAINT scrape_logs_pkey PRIMARY KEY (id), CONSTRAINT scrape_logs_scrape_run_id_fkey FOREIGN KEY (scrape_run_id) REFERENCES public.scrape_runs(id));
COMMENT ON TABLE public.scrape_logs IS 'Log lines emitted during a scrape run.';

-- Permissions

ALTER TABLE public.scrape_logs OWNER TO postgres;
GRANT ALL ON TABLE public.scrape_logs TO postgres;




-- Permissions

GRANT ALL ON SCHEMA public TO pg_database_owner;
GRANT USAGE ON SCHEMA public TO public;