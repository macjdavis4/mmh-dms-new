# Caddy with two extra modules:
#  - caddy-dns/cloudflare: Let's Encrypt certificates via the DNS challenge
#    (the HTTP challenge can't pass through Cloudflare's proxy reliably).
#  - caddy-cloudflare-ip: keeps the list of Cloudflare proxy IPs current so
#    the real visitor IP (CF-Connecting-IP) is trusted only from Cloudflare.
FROM caddy:2-builder AS builder
RUN xcaddy build \
    --with github.com/caddy-dns/cloudflare \
    --with github.com/WeidiDeng/caddy-cloudflare-ip

FROM caddy:2
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
COPY Caddyfile /etc/caddy/Caddyfile
