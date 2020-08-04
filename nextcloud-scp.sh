#!/bin/bash
rsync -vre ssh ../cosinnus-cloud/nextcloud/* root@<nextcloud-server>.de:/srv/nextcloud/<domain>/app/
rsync -vre ssh ./nextcloud/* root@<nextcloud-server>:/srv/nextcloud/<domain>/app/
