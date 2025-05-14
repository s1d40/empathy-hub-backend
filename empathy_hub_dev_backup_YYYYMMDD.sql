--
-- PostgreSQL database dump
--

-- Dumped from database version 15.13 (Debian 15.13-1.pgdg120+1)
-- Dumped by pg_dump version 15.13 (Ubuntu 15.13-1.pgdg24.04+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: chatavailabilityenum; Type: TYPE; Schema: public; Owner: empathy_hub_user
--

CREATE TYPE public.chatavailabilityenum AS ENUM (
    'OPEN_TO_CHAT',
    'REQUEST_ONLY',
    'DO_NOT_DISTURB'
);


ALTER TYPE public.chatavailabilityenum OWNER TO empathy_hub_user;

--
-- Name: votetypeenum_sqlalchemy; Type: TYPE; Schema: public; Owner: empathy_hub_user
--

CREATE TYPE public.votetypeenum_sqlalchemy AS ENUM (
    'UPVOTE',
    'DOWNVOTE'
);


ALTER TYPE public.votetypeenum_sqlalchemy OWNER TO empathy_hub_user;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: empathy_hub_user
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO empathy_hub_user;

--
-- Name: comments; Type: TABLE; Schema: public; Owner: empathy_hub_user
--

CREATE TABLE public.comments (
    id integer NOT NULL,
    anonymous_comment_id uuid NOT NULL,
    content text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone,
    post_id uuid NOT NULL,
    author_id uuid NOT NULL
);


ALTER TABLE public.comments OWNER TO empathy_hub_user;

--
-- Name: comments_id_seq; Type: SEQUENCE; Schema: public; Owner: empathy_hub_user
--

CREATE SEQUENCE public.comments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.comments_id_seq OWNER TO empathy_hub_user;

--
-- Name: comments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: empathy_hub_user
--

ALTER SEQUENCE public.comments_id_seq OWNED BY public.comments.id;


--
-- Name: post_vote_logs; Type: TABLE; Schema: public; Owner: empathy_hub_user
--

CREATE TABLE public.post_vote_logs (
    id integer NOT NULL,
    user_anonymous_id uuid NOT NULL,
    post_anonymous_id uuid NOT NULL,
    vote_type public.votetypeenum_sqlalchemy NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.post_vote_logs OWNER TO empathy_hub_user;

--
-- Name: post_vote_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: empathy_hub_user
--

CREATE SEQUENCE public.post_vote_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.post_vote_logs_id_seq OWNER TO empathy_hub_user;

--
-- Name: post_vote_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: empathy_hub_user
--

ALTER SEQUENCE public.post_vote_logs_id_seq OWNED BY public.post_vote_logs.id;


--
-- Name: posts; Type: TABLE; Schema: public; Owner: empathy_hub_user
--

CREATE TABLE public.posts (
    id integer NOT NULL,
    anonymous_post_id uuid NOT NULL,
    title character varying(100) NOT NULL,
    content text NOT NULL,
    author_anonymous_id uuid NOT NULL,
    is_active boolean NOT NULL,
    is_edited boolean NOT NULL,
    upvotes integer NOT NULL,
    downvotes integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone
);


ALTER TABLE public.posts OWNER TO empathy_hub_user;

--
-- Name: posts_id_seq; Type: SEQUENCE; Schema: public; Owner: empathy_hub_user
--

CREATE SEQUENCE public.posts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.posts_id_seq OWNER TO empathy_hub_user;

--
-- Name: posts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: empathy_hub_user
--

ALTER SEQUENCE public.posts_id_seq OWNED BY public.posts.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: empathy_hub_user
--

CREATE TABLE public.users (
    id integer NOT NULL,
    anonymous_id uuid NOT NULL,
    username character varying,
    bio text,
    avatar_url character varying,
    chat_availability public.chatavailabilityenum NOT NULL,
    pronouns character varying,
    is_active boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


ALTER TABLE public.users OWNER TO empathy_hub_user;

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: empathy_hub_user
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.users_id_seq OWNER TO empathy_hub_user;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: empathy_hub_user
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: comments id; Type: DEFAULT; Schema: public; Owner: empathy_hub_user
--

ALTER TABLE ONLY public.comments ALTER COLUMN id SET DEFAULT nextval('public.comments_id_seq'::regclass);


--
-- Name: post_vote_logs id; Type: DEFAULT; Schema: public; Owner: empathy_hub_user
--

ALTER TABLE ONLY public.post_vote_logs ALTER COLUMN id SET DEFAULT nextval('public.post_vote_logs_id_seq'::regclass);


--
-- Name: posts id; Type: DEFAULT; Schema: public; Owner: empathy_hub_user
--

ALTER TABLE ONLY public.posts ALTER COLUMN id SET DEFAULT nextval('public.posts_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: empathy_hub_user
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: empathy_hub_user
--

COPY public.alembic_version (version_num) FROM stdin;
a42a4cca84c4
\.


--
-- Data for Name: comments; Type: TABLE DATA; Schema: public; Owner: empathy_hub_user
--

COPY public.comments (id, anonymous_comment_id, content, created_at, updated_at, post_id, author_id) FROM stdin;
1	615a5237-f904-47cb-9f03-db92a2128a0a	string	2025-05-12 14:13:16.57425+00	\N	0068630f-ae05-499b-b0a9-c5404ff9bd19	cdf0905b-408c-4dfd-a090-663e234871f6
\.


--
-- Data for Name: post_vote_logs; Type: TABLE DATA; Schema: public; Owner: empathy_hub_user
--

COPY public.post_vote_logs (id, user_anonymous_id, post_anonymous_id, vote_type, created_at) FROM stdin;
1	cdf0905b-408c-4dfd-a090-663e234871f6	0068630f-ae05-499b-b0a9-c5404ff9bd19	UPVOTE	2025-05-12 14:06:12.773615+00
\.


--
-- Data for Name: posts; Type: TABLE DATA; Schema: public; Owner: empathy_hub_user
--

COPY public.posts (id, anonymous_post_id, title, content, author_anonymous_id, is_active, is_edited, upvotes, downvotes, created_at, updated_at) FROM stdin;
1	cc87ff0e-9b8b-47f3-9eca-ad1f977da42d	string	string	cdf0905b-408c-4dfd-a090-663e234871f6	t	f	0	0	2025-05-12 13:57:21.510115+00	\N
2	0068630f-ae05-499b-b0a9-c5404ff9bd19	string	SKIDUBIDUBIDUBIDUUUUUUU	cdf0905b-408c-4dfd-a090-663e234871f6	t	f	1	0	2025-05-12 13:57:40.685103+00	2025-05-12 14:06:12.773615+00
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: empathy_hub_user
--

COPY public.users (id, anonymous_id, username, bio, avatar_url, chat_availability, pronouns, is_active, created_at, updated_at) FROM stdin;
6	0116fa25-2544-4892-87ed-99e22d98d86f	string	string	string	OPEN_TO_CHAT	string	t	2025-05-12 03:29:04.348259+00	\N
7	bd7f280f-e01a-4b03-9d1e-3591cec1e051	AnonymousB4D0	string	https://i.pravatar.cc/150?u=bd7f280f-e01a-4b03-9d1e-3591cec1e051	OPEN_TO_CHAT		t	2025-05-12 03:30:05.381029+00	\N
8	461ce5f6-ba92-4817-881b-2dbe71d87842	testuser	string	https://i.pravatar.cc/150?u=461ce5f6-ba92-4817-881b-2dbe71d87842	OPEN_TO_CHAT		t	2025-05-12 03:52:40.452021+00	\N
9	d8176ca0-c068-413a-a2da-31f7d97d25d7	nelsao420	string	string	OPEN_TO_CHAT	string	t	2025-05-12 03:54:07.268644+00	\N
10	f08d9dff-0bdd-434a-9373-ddfc384b477a	Anonymous1C03	string	string	OPEN_TO_CHAT	string	t	2025-05-12 04:18:07.283546+00	\N
11	65fb709e-305e-463f-9790-c7998388b9b7	Anonymous24D1	string	string	OPEN_TO_CHAT	string	t	2025-05-12 04:36:00.492188+00	\N
12	a0ed4caf-0d91-40d0-8c35-1e87c9178549	Anonymous44C7	string	string	OPEN_TO_CHAT	string	t	2025-05-12 04:44:46.782429+00	\N
13	860ad0e7-3dbc-42a6-8162-a37d476e4c6e	Anonymous74B6	string	string	OPEN_TO_CHAT	string	t	2025-05-12 12:53:43.691608+00	\N
14	4cc4a322-5ed1-4a29-889a-cc9e82f322fd	AnonymousE222	string	https://i.pravatar.cc/150?u=4cc4a322-5ed1-4a29-889a-cc9e82f322fd	OPEN_TO_CHAT	string	t	2025-05-12 13:11:19.351038+00	\N
15	cdf0905b-408c-4dfd-a090-663e234871f6	AnonymousFA37	string	string	OPEN_TO_CHAT	string	t	2025-05-12 13:15:24.162063+00	\N
16	304160bf-7df2-430f-9999-61ea89456c60	Anonymous96AE	string	string	OPEN_TO_CHAT	string	t	2025-05-12 13:49:04.049112+00	\N
\.


--
-- Name: comments_id_seq; Type: SEQUENCE SET; Schema: public; Owner: empathy_hub_user
--

SELECT pg_catalog.setval('public.comments_id_seq', 1, true);


--
-- Name: post_vote_logs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: empathy_hub_user
--

SELECT pg_catalog.setval('public.post_vote_logs_id_seq', 1, true);


--
-- Name: posts_id_seq; Type: SEQUENCE SET; Schema: public; Owner: empathy_hub_user
--

SELECT pg_catalog.setval('public.posts_id_seq', 2, true);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: empathy_hub_user
--

SELECT pg_catalog.setval('public.users_id_seq', 16, true);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: empathy_hub_user
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: comments pk_comments; Type: CONSTRAINT; Schema: public; Owner: empathy_hub_user
--

ALTER TABLE ONLY public.comments
    ADD CONSTRAINT pk_comments PRIMARY KEY (id);


--
-- Name: post_vote_logs pk_post_vote_logs; Type: CONSTRAINT; Schema: public; Owner: empathy_hub_user
--

ALTER TABLE ONLY public.post_vote_logs
    ADD CONSTRAINT pk_post_vote_logs PRIMARY KEY (id);


--
-- Name: posts pk_posts; Type: CONSTRAINT; Schema: public; Owner: empathy_hub_user
--

ALTER TABLE ONLY public.posts
    ADD CONSTRAINT pk_posts PRIMARY KEY (id);


--
-- Name: post_vote_logs uq_post_vote_logs_user_anonymous_id_post_anonymous_id; Type: CONSTRAINT; Schema: public; Owner: empathy_hub_user
--

ALTER TABLE ONLY public.post_vote_logs
    ADD CONSTRAINT uq_post_vote_logs_user_anonymous_id_post_anonymous_id UNIQUE (user_anonymous_id, post_anonymous_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: empathy_hub_user
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: ix_comments_anonymous_comment_id; Type: INDEX; Schema: public; Owner: empathy_hub_user
--

CREATE UNIQUE INDEX ix_comments_anonymous_comment_id ON public.comments USING btree (anonymous_comment_id);


--
-- Name: ix_comments_author_id; Type: INDEX; Schema: public; Owner: empathy_hub_user
--

CREATE INDEX ix_comments_author_id ON public.comments USING btree (author_id);


--
-- Name: ix_comments_id; Type: INDEX; Schema: public; Owner: empathy_hub_user
--

CREATE INDEX ix_comments_id ON public.comments USING btree (id);


--
-- Name: ix_comments_post_id; Type: INDEX; Schema: public; Owner: empathy_hub_user
--

CREATE INDEX ix_comments_post_id ON public.comments USING btree (post_id);


--
-- Name: ix_post_vote_logs_id; Type: INDEX; Schema: public; Owner: empathy_hub_user
--

CREATE INDEX ix_post_vote_logs_id ON public.post_vote_logs USING btree (id);


--
-- Name: ix_post_vote_logs_post_anonymous_id; Type: INDEX; Schema: public; Owner: empathy_hub_user
--

CREATE INDEX ix_post_vote_logs_post_anonymous_id ON public.post_vote_logs USING btree (post_anonymous_id);


--
-- Name: ix_post_vote_logs_user_anonymous_id; Type: INDEX; Schema: public; Owner: empathy_hub_user
--

CREATE INDEX ix_post_vote_logs_user_anonymous_id ON public.post_vote_logs USING btree (user_anonymous_id);


--
-- Name: ix_posts_anonymous_post_id; Type: INDEX; Schema: public; Owner: empathy_hub_user
--

CREATE UNIQUE INDEX ix_posts_anonymous_post_id ON public.posts USING btree (anonymous_post_id);


--
-- Name: ix_posts_author_anonymous_id; Type: INDEX; Schema: public; Owner: empathy_hub_user
--

CREATE INDEX ix_posts_author_anonymous_id ON public.posts USING btree (author_anonymous_id);


--
-- Name: ix_posts_id; Type: INDEX; Schema: public; Owner: empathy_hub_user
--

CREATE INDEX ix_posts_id ON public.posts USING btree (id);


--
-- Name: ix_posts_title; Type: INDEX; Schema: public; Owner: empathy_hub_user
--

CREATE INDEX ix_posts_title ON public.posts USING btree (title);


--
-- Name: ix_users_anonymous_id; Type: INDEX; Schema: public; Owner: empathy_hub_user
--

CREATE UNIQUE INDEX ix_users_anonymous_id ON public.users USING btree (anonymous_id);


--
-- Name: ix_users_id; Type: INDEX; Schema: public; Owner: empathy_hub_user
--

CREATE INDEX ix_users_id ON public.users USING btree (id);


--
-- Name: ix_users_username; Type: INDEX; Schema: public; Owner: empathy_hub_user
--

CREATE UNIQUE INDEX ix_users_username ON public.users USING btree (username);


--
-- Name: comments fk_comments_author_id_users; Type: FK CONSTRAINT; Schema: public; Owner: empathy_hub_user
--

ALTER TABLE ONLY public.comments
    ADD CONSTRAINT fk_comments_author_id_users FOREIGN KEY (author_id) REFERENCES public.users(anonymous_id);


--
-- Name: comments fk_comments_post_id_posts; Type: FK CONSTRAINT; Schema: public; Owner: empathy_hub_user
--

ALTER TABLE ONLY public.comments
    ADD CONSTRAINT fk_comments_post_id_posts FOREIGN KEY (post_id) REFERENCES public.posts(anonymous_post_id);


--
-- Name: post_vote_logs fk_post_vote_logs_post_anonymous_id_posts; Type: FK CONSTRAINT; Schema: public; Owner: empathy_hub_user
--

ALTER TABLE ONLY public.post_vote_logs
    ADD CONSTRAINT fk_post_vote_logs_post_anonymous_id_posts FOREIGN KEY (post_anonymous_id) REFERENCES public.posts(anonymous_post_id);


--
-- Name: post_vote_logs fk_post_vote_logs_user_anonymous_id_users; Type: FK CONSTRAINT; Schema: public; Owner: empathy_hub_user
--

ALTER TABLE ONLY public.post_vote_logs
    ADD CONSTRAINT fk_post_vote_logs_user_anonymous_id_users FOREIGN KEY (user_anonymous_id) REFERENCES public.users(anonymous_id);


--
-- Name: posts fk_posts_author_anonymous_id_users; Type: FK CONSTRAINT; Schema: public; Owner: empathy_hub_user
--

ALTER TABLE ONLY public.posts
    ADD CONSTRAINT fk_posts_author_anonymous_id_users FOREIGN KEY (author_anonymous_id) REFERENCES public.users(anonymous_id);


--
-- PostgreSQL database dump complete
--

