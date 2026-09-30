## Before
No retry budget existed for the BM25 retrieval loop.

## After
- `src/retrieval_config.py` — Add a retry_limit configuration knob to the BM25 retrieval loop.
- `src/oauth_login.py` — Add a Google OAuth login screen for the admin dashboard.
