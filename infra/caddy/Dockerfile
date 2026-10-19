# Caddy with two extra modules:
#  - caddy-dns/cloudflare: Let's Encrypt certificates via the DNS challenge
#    (the HTTP challenge can't pass through Cloudflare's proxy reliably).
#  - caddy-cloudflare-ip: keeps the list of Cloudflare proxy IPs current so
#    the real visitor IP (CF-Connecting-IP) is trusted only from Cloudflare.
FROM caddy:2-builder AS builder
# Modules are pinned to exact versions: this binary faces the internet, so a
# rebuild must never pull in whatever was pushed to a module's main branch.
# golang.org/x/net is pinned above Caddy's own version to pick up the fix for
# CVE-2026-78669 (HTTP/2 denial of service). Remove once Caddy ships >= 0.60.0.
RUN xcaddy build \
    --with github.com/caddy-dns/cloudflare@v0.2.4 \
    --with github.com/WeidiDeng/caddy-cloudflare-ip@v0.0.0-20231130002422-f53b62aa13cb \
    --replace golang.org/x/net=golang.org/x/net@v0.60.0

FROM caddy:2
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
COPY Caddyfile /etc/caddy/Caddyfile
