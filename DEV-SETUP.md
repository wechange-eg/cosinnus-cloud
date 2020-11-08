# Developer Setup (WIP)

The setup is currently more complex that it needs to be, this will be improved later.

First, make sure you have the submodules:
```
$ git submodule update --init
```

You need:

- Docker-Compose
- an nginx installation (that will proxy the docker nginx that proxies another docker nginx...)

# Edit /etc/hosts

add an entry

```
127.0.0.1 wechange-dev
```

# create a nginx proxy site

install nginx on your OS, this guide assumes you use a debia based distro.

in /etc/nginx/sites-available, add a new file "wechange" (name is not important) with the following contents:

```
server {
    listen 80;
    server_name wechange-dev;
    access_log /tmp/nginx.log;

    location /nextcloud/ {
        proxy_pass http://127.0.0.1:8080/;
        proxy_redirect off;
        proxy_set_header Host $host;

        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location / {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host $host;
        proxy_redirect off;
    }
}
```

then go to /etc/nginx/sites-enabled and create a symlink

ln -s ../sites-available/wechange

then restart nginx.

# Start nextcloud

cd to nextcloud-docker and execute

\$ docker-compose up db

and then wait until you see "database system is ready to accept connections"; you can then press Ctrl-C to stop the container.
This step ensures that the database will be available quickly once the app container starts (there seems to be a race condition that prevents nextcloud from initializing correctly if the database is not reachable). This step is only necessary once.

Then do

\$ docker-compose up -d

you can also omit the `-d` if you want to see the log output without having to execute docker-compose logs

# Update the config.php file in the container

\$ docker-compose logs -f app

Now wait until you see "Nextcloud was sucessfully installed"

```
Attaching to nextcloud-docker_app_1
app_1        | Initializing nextcloud 18.0.0.10 ...
app_1        | Initializing finished
app_1        | New nextcloud instance
app_1        | Installing with PostgreSQL database
app_1        | starting nextcloud installation
app_1        | Nextcloud was successfully installed
app_1        | setting trusted domains…
app_1        | System config value trusted_domains => 1 set to string wechange-dev
app_1        | [18-Dec-2019 16:26:45] NOTICE: fpm is running, pid 1
app_1        | [18-Dec-2019 16:26:45] NOTICE: ready to handle connections
```

press Ctrl+C

then do (the docker-compose container must be running for this to work)

$ docker-compose exec app su www-data -s /bin/sh -c './occ config:system:set overwritewebroot --value /nextcloud'
$ docker-compose exec app su www-data -s /bin/sh -c 'for x in onlyoffice sociallogin groupfolders; do ./occ app:install \$x;done'

You should now be able to visit http://wechange-dev/nextcloud and see the login screen

# Configure oauth2 application in cosinnus

At the time of writing, the oauth2_provider application config interface is broken, so we have to add the data manually. Connect to your WECHANGE Postgres database (not the postgres used in docker-compose; that one is used by Nextcloud), and execute:

```
insert into oauth2_provider_application (client_id, client_secret, client_type, redirect_uris, authorization_grant_type, name, skip_authorization, created, updated) values ('foobar', 'barfoo', 'public', 'http://wechange-dev/nextcloud/apps/sociallogin/custom_oauth2/wechange', 'authorization-code', 'nextcloud', true, now(), now());
```

Obviously, "foobar"/"barfoo" should not be used in production.

# Configure necessary modules

Go to http://wechange-dev/nextcloud/settings/admin/sociallogin (log in as "admin", password "admin")

Activate "update user profile at login", and add a new Custom OAuth Server (not Custom OpenID Connect)

- Internal name: wechange
- Name: wechange
- API-Base: http://wechange-dev/o
- Authorize-URL: http://wechange-dev/o/authorize/ (contrary to what the UI claims, the url cannot be relative)
- Token-URL: http://wechange-dev/o/token/ (mind the trailing slash)
- Profile-URL: http://wechange-dev/group/forum/cloud/oauth2/
- Logout-URL: (empty)
- Client ID: foobar
- Client Secret: barfoo
- Scope: read

Then save

Go to http://wechange-dev/nextcloud/settings/admin/onlyoffice

- Document Editing Service address: /nextcloud/oo/
- Advanced Server Settings
  - Document Editing Service address for internal requests from the server: http://onlyoffice/
  - Server address for internal requests from the Document Editing Service: http://wechange-dev/nextcloud/

and save.

Now go to http://wechange-dev/nextcloud/settings/users and add a new group named "wechange-Forum"

# Add settings to settings.py

- Add "wechange-dev" to ALLOWED_HOSTS

Add

```
COSINNUS_CLOUD_NEXTCLOUD_URL = "http://wechange-dev/nextcloud"
COSINNUS_CLOUD_NEXTCLOUD_ADMIN_USERNAME = "admin"
COSINNUS_CLOUD_NEXTCLOUD_AUTH = ("admin", "admin")
```

Change domainname in http://localhost/admin/sites/site to wechange-dev

# You're set

You should be able to visit http://wechange-dev/group/forum/cloud and log in by clicking on "login with wechange". If you get an
internal error that wechange-dev cannot be reached, the docker ip might have changed. Do `ip addr` again and edit the "wechange-dev:172.x.x.x" entry in the docker-compose.yml file, then do `docker-compose restart`
