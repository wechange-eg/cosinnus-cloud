#!/bin/bash
rsync -ave ssh ../cosinnus-cloud/nextcloud/* root@<nextcloud-server>.de:/srv/nextcloud/<domain>/app/
rsync -ave ssh -r ./nextcloud/* root@<nextcloud-server>:/srv/nextcloud/<domain>/app/
