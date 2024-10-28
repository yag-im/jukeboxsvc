# jukeboxsvc

jukeboxsvc is a service governing jukebox cluster

## refresh docker image on a cluster node [jukebox node]

    AWS_PROFILE=ecr-ro docker pull 070143334704.dkr.ecr.us-east-1.amazonaws.com/im.acme.yag.jukebox:x11_gpu-intel_scummvm_2.8.0_20240218

# release a new version

Inside a devcontainer:

    make lint
    make build

Outside of a devcontainer:

    make docker-build
    make docker-run
    make docker-pub TAG=0.0.20
