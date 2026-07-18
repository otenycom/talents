# Clone neutralize — portal connection

At clone time the platform repoints `connections.portal` to the stub double. Before
the bot serves a turn, confirm:

1. `OTENY_CONN_PORTAL_BASE_URL` resolves to your tunnelled demo portal (or another
   non-prod stub), **not** `https://permits.example.org`.
2. The browser fence blocks navigation to `permits.example.org` on non-prod tiers.
