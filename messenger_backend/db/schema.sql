create extension if not exists vector;

create table if not exists public.barangay_documents (
    id bigint generated always as identity primary key,
    title text not null,
    content text not null,
    source_url text not null,
    page_number integer,
    document_type text not null,
    metadata jsonb not null default '{}'::jsonb,
    embedding vector(1536) not null,
    search_vector tsvector generated always as
        (to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(content, ''))) stored,
    created_at timestamptz not null default now()
);

create index if not exists barangay_documents_embedding_idx
    on public.barangay_documents using hnsw (embedding vector_cosine_ops);
create index if not exists barangay_documents_search_idx
    on public.barangay_documents using gin (search_vector);

alter table public.barangay_documents enable row level security;
revoke all on public.barangay_documents from anon, authenticated;
grant all on public.barangay_documents to service_role;

create or replace function public.hybrid_search_barangay_documents(
    query_text text,
    query_embedding vector(1536),
    match_count integer default 6
)
returns table (
    id bigint,
    title text,
    content text,
    source_url text,
    page_number integer,
    document_type text,
    semantic_score double precision,
    keyword_score real
)
language sql
stable
as $$
    with candidates as (
        select d.*,
               1 - (d.embedding <=> query_embedding) as semantic_score,
               ts_rank_cd(d.search_vector, websearch_to_tsquery('simple', query_text)) as keyword_score
        from public.barangay_documents as d
        where d.search_vector @@ websearch_to_tsquery('simple', query_text)
           or d.embedding <=> query_embedding < 0.8
    )
    select c.id, c.title, c.content, c.source_url, c.page_number, c.document_type,
           c.semantic_score, c.keyword_score
    from candidates as c
    order by (0.65 * c.semantic_score + 0.35 * c.keyword_score) desc
    limit greatest(1, least(match_count, 12));
$$;

revoke all on function public.hybrid_search_barangay_documents(text, vector, integer) from public;
grant execute on function public.hybrid_search_barangay_documents(text, vector, integer) to service_role;

comment on table public.barangay_documents is
    'Curated, chunked Citizen''s Charter and local ordinance content. Never place resident messages here.';
