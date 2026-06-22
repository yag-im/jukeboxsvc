import re

from jukeboxsvc.biz.ovh_defs import NodeServiceType
from jukeboxsvc.dto.container import DcRegion


def node_ix_from_instance_name(name: str) -> int:
    """Extracts the node index from the instance name (e.g. 'jukebox34-us-west-1' -> 34)."""
    first_token = name.split("-")[0]
    match = re.search(r"\d+", first_token)
    if not match:
        raise ValueError(f"Invalid instance name format: {name}")
    return int(match.group())


def node_ix_to_private_ip(node_service: NodeServiceType, region: DcRegion, node_ix: int) -> str:
    """Converts a node index to a private IP address in the OVH private network."""
    if region == DcRegion.US_EAST_1:
        ip_prefix = 12
    elif region == DcRegion.US_WEST_1:
        ip_prefix = 13
    else:
        raise ValueError(f"Unsupported region: {region}")
    if node_service == NodeServiceType.JUKEBOX:
        return f"192.168.{ip_prefix}.{2 + node_ix}"
    elif node_service == NodeServiceType.APPSTOR:
        return f"192.168.{ip_prefix}.{200 + node_ix}"
    else:
        raise ValueError(f"Unsupported node service: {node_service}")


def private_ip_to_node_ix(node_service: NodeServiceType, private_ip: str) -> int:
    """Extracts the node index from a private IP address in the OVH private network."""
    last_octet = int(private_ip.split(".")[-1])
    if node_service == NodeServiceType.JUKEBOX:
        return last_octet - 2
    elif node_service == NodeServiceType.APPSTOR:
        return last_octet - 200
    else:
        raise ValueError(f"Unsupported node service: {node_service}")


def build_appstor_image_user_data(region: DcRegion, node_ix: int, btrfs_devices: str) -> str:
    private_ip = node_ix_to_private_ip(NodeServiceType.APPSTOR, region, node_ix)
    return (
        "#cloud-config\n"
        "write_files:\n"
        "  - path: /etc/appstor/boot.env\n"
        "    permissions: '0644'\n"
        "    owner: root:root\n"
        "    content: |\n"
        f"      APPSTOR_NODE_PRIVATE_IP={private_ip}\n"
        f"      BTRFS_DEVICES={btrfs_devices}\n"
        f"      CLUSTER_REGION={region}\n"
        f"      NODE_INDEX={node_ix}\n"
        f"      FQDN_HOST_PREFIX=appstor\n"
        "\n"
        "runcmd:\n"
        "  - |\n"
        f'    priv=$(ip -4 -o addr show | awk -v ip="{private_ip}" \'$4~("^"ip"/"){{print $2;exit}}\')'
        "\n"
        "    gw=$(ip route show dev \"$priv\" | awk '/^default/{print $3;exit}')"
        "\n"
        '    ip route del default dev "$priv" 2>/dev/null; ip route add default via "$gw" dev "$priv" metric 200'
        "\n"
    )


def build_jukebox_image_user_data(region: DcRegion, node_ix: int, appstor_num: int) -> str:
    private_ip = node_ix_to_private_ip(NodeServiceType.JUKEBOX, region, node_ix)
    return (
        "#cloud-config\n"
        "write_files:\n"
        "  - path: /etc/jukebox/boot.env\n"
        "    permissions: '0644'\n"
        "    owner: root:root\n"
        "    content: |\n"
        f"      JUKEBOX_NODE_PRIVATE_IP={private_ip}\n"
        f"      APPSTOR_NUM={appstor_num}\n"
        f"      NODE_INDEX={node_ix}\n"
        f"      FQDN_HOST_PREFIX=jukebox\n"
        f"      CLUSTER_REGION={region}\n"
        "\n"
        "runcmd:\n"
        "  - |\n"
        f'    priv=$(ip -4 -o addr show | awk -v ip="{private_ip}" \'$4~("^"ip"/"){{print $2;exit}}\')'
        "\n"
        "    gw=$(ip route show dev \"$priv\" | awk '/^default/{print $3;exit}')"
        "\n"
        '    ip route del default dev "$priv" 2>/dev/null; ip route add default via "$gw" dev "$priv" metric 200'
        "\n"
    )
