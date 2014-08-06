"""Cloudify tasks that operate docker containers using python docker api"""

import docker

from cloudify import exceptions
from cloudify.decorators import operation

import docker_plugin.apt_get_wrapper as apt_get_wrapper
import docker_plugin.docker_wrapper as docker_wrapper


_ERR_MSG_NO_IMAGE_SRC = 'Either path or url to image must be given'


@operation
def create(ctx, *args, **kwargs):
    """Create container.

    RPC called by Cloudify Manager.

    Import image from ctx.properties['image_import'] with optional
    options from ctx.properties['image_import'].
    'src' in ctx.properties['image_import'] must be specified.

    Set imported image_id in ctx.runtime_properties['image'].

    Set variables from ctx.properties that are not used by cloudify plugin
    to enviromental variables, which will be added to variables from
    ctx.properties['container_create']['enviroment'] and relayed to container.

    Create container from imported image with options from
    ctx.properties['container_create'].
    'command' in ctx.properties['container_create'] must be specified.

    Args:
        ctx (cloudify context)

    Raises:
        NonRecoverableError: when 'src' in ctx.properties['image_import']
            is not specified
            or when docker.errors.APIError during start (for example when
            'command' is not specified in ctx.properties['container_create'].

    """
    apt_get_wrapper.install_docker(ctx)
    client = docker_wrapper.get_client(ctx)
    if ctx.properties.get('image_import', {}).get('src'):
        image = docker_wrapper.import_image(ctx, client)
    elif ctx.properties.get('image_build', {}).get('path'):
        image = docker_wrapper.build_image(ctx, client)
    else:
        ctx.logger.error(_ERR_MSG_NO_IMAGE_SRC)
        raise exceptions.NonRecoverableError(_ERR_MSG_NO_IMAGE_SRC)
    ctx.runtime_properties['image'] = image
    docker_wrapper.set_env_var(ctx, client)
    docker_wrapper.create_container(ctx, client)


@operation
def run(ctx, *args, **kwargs):
    """Run container.

    RPC called by Cloudify Manager.

    Run container which id is specified in ctx.runtime_properties['container']
    with optional options from ctx.properties['container_start'].

    Get ports, top and host ip information from container using containers
    function.

    Args:
        ctx (cloudify context)

    Raises:
        NonRecoverableError: when 'container' in ctx.runtime_properties is None
            or when docker.errors.APIError during start.

    Logs:
       Container id,
       Container ports,
       Container top information,
       TODO(Michal) host ip

    """
    client = docker_wrapper.get_client(ctx)
    docker_wrapper.start_container(ctx, client)
    container = docker_wrapper.get_container_info(ctx, client)
    log_msg = 'Container: {}\nPorts: {}\nTop: {}'.format(
        container['Id'],
        str(container['Ports']),
        docker_wrapper.get_top_info(ctx, client)
    )
    ctx.logger.info(log_msg)


@operation
def stop(ctx, *args, **kwargs):
    """Stop container.

    RPC called by Cloudify Manager.

    Stop container which id is specified in ctx.runtime_properties
    ['container'] with optional options from ctx.properties['container_stop'].

    Args:
        ctx (cloudify context)

    Raises:
        NonRecoverableError: when 'container' in ctx.runtime_properties is None
            or when docker.errors.APIError during stop.

    """
    client = docker_wrapper.get_client(ctx)
    docker_wrapper.stop_container(ctx, client)


@operation
def delete(ctx, *args, **kwargs):
    """Delete container.

    RPC called by Cloudify Manager.

    Remove container which id is specified in ctx.runtime_properties
    ['container'] with optional options from
    ctx.properties['container_remove'].

    If container is running stop it.
    if ctx['container_remove']['remove_image'] is True then remove image.

    Args:
        ctx (cloudify context)

    Raises:
        NonRecoverableError: when 'container' in ctx.runtime_properties is None
            or 'remove_image' in ctx.properties['container_remove'] is True
            and 'image' in ctx.runtime_properties is None
            or when docker.errors.APIError during stop, remove_container,
            remove_image (for example if image is used by another container).

    """
    client = docker_wrapper.get_client(ctx)
    container_info = docker_wrapper.inspect_container(ctx, client)
    if container_info and container_info['State']['Running']:
        docker_wrapper.stop_container(ctx, client)
    remove_image = ctx.properties.get('container_remove', {}).pop(
        'remove_image', None
    )
    docker_wrapper.remove_container(ctx, client)
    if remove_image:
        docker_wrapper.remove_image(ctx, client)
