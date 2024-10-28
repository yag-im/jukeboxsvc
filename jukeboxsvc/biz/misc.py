import base64
import logging
import os
import typing as t

import boto3
import docker

DOCKER_CLIENT_VER = "1.45"
DOCKER_CLIENT_TIMEOUT = 10

log = logging.getLogger("jukeboxsvc")


@t.no_type_check
def log_input_output(func):
    def wrap(*args, **kwargs):
        # Log the function name and arguments
        log.debug("calling %s with args: %s, kwargs: %s", func.__name__, args, kwargs)

        # Call the original function
        result = func(*args, **kwargs)

        # Log the return value
        log.debug("%s returned: %s", func.__name__, repr(result))

        # Return the result
        return result

    return wrap


def get_cluster_client(
    api_uri: str, ecr_login: bool = False, timeout: int = DOCKER_CLIENT_TIMEOUT
) -> docker.DockerClient:
    client = docker.DockerClient(base_url=api_uri, timeout=timeout, version=DOCKER_CLIENT_VER)
    # TODO: watch for https://github.com/docker/docker-py/issues/3217 and drop "if" below once resolved
    # use only for pulling images, do not use on container runs (make sure image is prepopulated on all cluster nodes)
    # aws sets rate limits on ecr endpoints and this call often fails
    if ecr_login:
        aws_ecr_access_key = os.environ["AWS_ECR_ACCESS_KEY"]
        aws_ecr_secret_key = os.environ["AWS_ECR_SECRET_KEY"]
        aws_ecr_region = os.environ["AWS_ECR_REGION"]
        session = boto3.Session(
            aws_access_key_id=aws_ecr_access_key,
            aws_secret_access_key=aws_ecr_secret_key,
            region_name=aws_ecr_region,
        )
        ecr = session.client("ecr")
        response = ecr.get_authorization_token()
        username, password = (
            base64.b64decode(response["authorizationData"][0]["authorizationToken"]).decode().split(":")
        )
        registry = response["authorizationData"][0]["proxyEndpoint"]
        client.login(username, password, registry=registry)
    return client
