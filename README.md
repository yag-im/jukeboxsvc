# jukeboxsvc

Service governing *jukebox* cluster.

## Development

### Prerequisite

Make sure ports data directory exists on the host machine:

    ~/yag/data/ports

and contains `apps` and `clones` folders.

jukeboxsvc will perform a local copy from `apps` to `clones` on the app run event.

Also make sure `appstor-vol` docker volume (sourced from ~/yag/data/ports/clones) was created on the host machine:

    docker volume create --driver local \
        --opt type=none \
        --opt o=bind \
        --opt device=~/yag/data/ports/clones \
        appstor-vol

This volume will be mounted inside the jukebox docker container on the app start.

Create *.devcontainer/secrets.env* file:

    SIGNALER_AUTH_TOKEN=***VALUE***

Make sure:

    IGPU_CARD_ID
    IGPU_RENDER_DEVICE_ID

in `.devcontainer/.env` contain proper values.
TODO: automate card detection and selection on the jukebox node end

Then simply open this project in any IDE that supports devcontainers (VSCode is recommended).
