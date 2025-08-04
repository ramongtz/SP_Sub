# frontend.Dockerfile
# --- Instructions to build a secure Nginx container ---

# Start from the latest stable and secure version of Nginx on Alpine
FROM nginx:alpine

# --- NEW: Apply OS-level security patches ---
# This will update packages like expat, curl, openssl, etc. to their patched versions
RUN apk update && apk upgrade

# Copy the Nginx configuration and the application's main page
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html /usr/share/nginx/html/index.html