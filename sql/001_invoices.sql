-- Intelligent Document Processing: schema for Supabase (PostgreSQL 15+).
-- Run once in the Supabase SQL editor. Safe to run again.

create extension if not exists pgcrypto;

-- n8n keeps its own tables (workflows, credentials, executions) in a separate schema.
create schema if not exists n8n;

-- Supplier master data. The n8n workflow and Jev use the same 15 keys.
create table if not exists public.vendors (
    key        text primary key,
    name       text not null,
    vat_id     text,
    iban       text,
    created_at timestamptz not null default now()
);

insert into public.vendors (key, name, vat_id, iban) values
    ('telekom',            'Telekom Deutschland GmbH',                                 'DE811904217', 'DE31370100500248586505'),
    ('aws',                'Amazon Web Services EMEA SARL, Niederlassung Deutschland', 'DE317013094', 'DE32700202700015840926'),
    ('brenner',            'Brenner Bürobedarf GmbH',                                  'DE291847366', null),
    ('westfalen_logistik', 'Westfalen Logistik Kühn KG',                               'DE276103958', null),
    ('lindner_it',         'Lindner IT-Service GmbH',                                  'DE305572814', null),
    ('ems_energie',        'Ems-Energie Versorgung GmbH',                              'DE284019375', null),
    ('autohaus_hesse',     'Autohaus Hesse GmbH & Co. KG',                             'DE213958604', null),
    ('klar_reinigung',     'Klar Gebäudereinigung GmbH',                               'DE299384710', null),
    ('kanzlei_moeller',    'Steuerkanzlei Möller & Partner mbB',                       'DE267731049', null),
    ('cloudwerk',          'Cloudwerk Software GmbH',                                  'DE322190486', null),
    ('druckerei_hansen',   'Druckerei Hansen e.K.',                                    'DE258830172', null),
    ('vogt_immobilien',    'Vogt Immobilien & Gewerbevermietung GmbH',                 'DE281164093', null),
    ('stahlmann',          'Stahlmann Werkzeughandel GmbH',                            'DE249906618', null),
    ('feldkueche',         'Feldküche Catering GmbH',                                  'DE313347722', null),
    ('nordpapier',         'Nordpapier Großhandel GmbH',                               'DE266058831', null)
on conflict (key) do nothing;

-- Every submitted document lands here: approved invoices and the review queue.
create table if not exists public.invoices (
    id                    uuid primary key default gen_random_uuid(),
    vendor                text,
    vendor_key            text not null default 'unknown',
    document_type         text not null,
    invoice_number        text,
    invoice_date          date,
    total_net             numeric(12, 2),
    tax_rate              numeric(5, 2),
    total_tax             numeric(12, 2),
    total_gross           numeric(12, 2),
    status                text not null check (status in ('approved', 'needs_review')),
    jev_confidence        numeric(4, 3) check (jev_confidence between 0 and 1),
    jev_answers           jsonb,
    human_review_required boolean not null,
    review_reasons        text[] not null default '{}',
    haiku_summary         text,
    notes                 text[] not null default '{}',
    latency_ms            jsonb,
    source                text,
    created_at            timestamptz not null default now(),
    constraint review_flag_matches_status
        check (human_review_required = (status = 'needs_review'))
);

-- An invoice number can be booked only once per supplier.
create unique index if not exists invoices_one_booking_per_number
    on public.invoices (vendor_key, upper(regexp_replace(invoice_number, '\s', '', 'g')))
    where status = 'approved';

create index if not exists invoices_review_queue
    on public.invoices (created_at desc)
    where status = 'needs_review';

-- Duplicates are caught inside the database, so two submissions of the same invoice
-- can never both be booked, whatever happens in the workflow.
create or replace function public.route_duplicate_invoice()
returns trigger
language plpgsql
as $$
begin
    if new.status = 'approved' and exists (
        select 1
        from public.invoices booked
        where booked.status = 'approved'
          and booked.vendor_key = new.vendor_key
          and upper(regexp_replace(booked.invoice_number, '\s', '', 'g'))
            = upper(regexp_replace(new.invoice_number, '\s', '', 'g'))
    ) then
        new.status := 'needs_review';
        new.human_review_required := true;
        new.review_reasons := array_append(new.review_reasons, 'invoice already booked');
    end if;
    return new;
end;
$$;

drop trigger if exists invoices_route_duplicate on public.invoices;
create trigger invoices_route_duplicate
    before insert on public.invoices
    for each row execute function public.route_duplicate_invoice();

-- No public access: only the secret key used by n8n (role service_role) may read and write.
alter table public.vendors  enable row level security;
alter table public.invoices enable row level security;
revoke all on public.vendors, public.invoices from anon, authenticated;
grant usage on schema public to service_role;
grant select on public.vendors to service_role;
grant select, insert, update on public.invoices to service_role;
