-- ============================================================
-- ExpediRamp — Supabase Database Schema
-- Run this in the Supabase SQL Editor to set up your tables.
-- ============================================================

-- Enable UUID generation
create extension if not exists "uuid-ossp";

-- ── Conversations ─────────────────────────────────────────────
create table public.conversations (
    id          uuid primary key default uuid_generate_v4(),
    user_id     uuid not null references auth.users(id) on delete cascade,
    title       text not null default 'New Trip',
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);

alter table public.conversations enable row level security;

create policy "Users see own conversations"
    on public.conversations for select
    using (auth.uid() = user_id);

create policy "Users create own conversations"
    on public.conversations for insert
    with check (auth.uid() = user_id);

create policy "Users update own conversations"
    on public.conversations for update
    using (auth.uid() = user_id);

create policy "Users delete own conversations"
    on public.conversations for delete
    using (auth.uid() = user_id);

-- Auto-update updated_at
create or replace function public.set_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

create trigger conversations_updated_at
    before update on public.conversations
    for each row execute function public.set_updated_at();


-- ── Messages ──────────────────────────────────────────────────
create table public.messages (
    id              uuid primary key default uuid_generate_v4(),
    conversation_id uuid not null references public.conversations(id) on delete cascade,
    role            text not null check (role in ('user', 'assistant', 'system')),
    content         text not null,
    metadata        jsonb,
    created_at      timestamptz not null default now()
);

create index idx_messages_conversation on public.messages(conversation_id, created_at);

alter table public.messages enable row level security;

create policy "Users see messages in own conversations"
    on public.messages for select
    using (
        exists (
            select 1 from public.conversations c
            where c.id = conversation_id and c.user_id = auth.uid()
        )
    );

create policy "Users insert messages in own conversations"
    on public.messages for insert
    with check (
        exists (
            select 1 from public.conversations c
            where c.id = conversation_id and c.user_id = auth.uid()
        )
    );

-- Also update the parent conversation's updated_at on new message
create or replace function public.touch_conversation()
returns trigger as $$
begin
    update public.conversations set updated_at = now() where id = new.conversation_id;
    return new;
end;
$$ language plpgsql;

create trigger messages_touch_conversation
    after insert on public.messages
    for each row execute function public.touch_conversation();


-- ── Itineraries ───────────────────────────────────────────────
create table public.itineraries (
    id              uuid primary key default uuid_generate_v4(),
    conversation_id uuid not null references public.conversations(id) on delete cascade,
    user_id         uuid not null references auth.users(id) on delete cascade,
    data            jsonb not null,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now(),

    unique (conversation_id)
);

alter table public.itineraries enable row level security;

create policy "Users see own itineraries"
    on public.itineraries for select
    using (auth.uid() = user_id);

create policy "Users upsert own itineraries"
    on public.itineraries for insert
    with check (auth.uid() = user_id);

create policy "Users update own itineraries"
    on public.itineraries for update
    using (auth.uid() = user_id);

create trigger itineraries_updated_at
    before update on public.itineraries
    for each row execute function public.set_updated_at();


-- ── Indexes for performance ───────────────────────────────────
create index idx_conversations_user on public.conversations(user_id, updated_at desc);
create index idx_itineraries_user on public.itineraries(user_id, updated_at desc);
