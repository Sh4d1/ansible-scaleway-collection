# Copyright (c) 2017 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)

__metaclass__ = type

DOCUMENTATION = '''
    name: scaleway
    plugin_type: inventory
    author:
      - Remy Leone (@sieben)
    short_description: Scaleway inventory source
    description:
        - Get inventory hosts from Scaleway
    options:
        plugin:
            description: token that ensures this is a source file for the 'scaleway' plugin.
            required: True
            choices: ['scaleway']
        zones:
            description: Filter results on a specific Scaleway region
            type: list
            default:
                - nl-ams-1
                - fr-par-1
        tags:
            description: Filter results on a specific tag
            type: list
        mandatory_tags:
            description: Filter result always matching all these tags - Added in Ansible 2.8
            type: list
        exclude_tags:
            description: Exclude specific tags - Added in Ansible 2.8
            type: list
        oauth_token:
            required: True
            description: Scaleway OAuth token.
            env:
                # in order of precedence
                - name: SCW_TOKEN
                - name: SCW_API_KEY
                - name: SCW_OAUTH_TOKEN
        api_url:
            required: False
            description: Scaleway API URL
            default: https://api.scaleway.com
            env:
                - name: SCW_API_URL
        organization_id:
            description: Organization ID to use
            env:
                - name: SCW_ORGANIZATION_ID
                - name: SCW_DEFAULT_ORGANIZATION_ID
        hostnames:
            description: List of preference about what to use as an hostname.
            type: list
            default:
                - public_ipv4
            choices:
                - public_ipv4
                - private_ipv4
                - public_ipv6
                - hostname
                - id
        variables:
            description: 'set individual variables: keys are variable names and
                          values are templates. Any value returned by the
                          L(Scaleway API, https://developer.scaleway.com/#servers-server-get)
                          can be used.'
            type: dict
'''

EXAMPLES = '''
# scaleway_inventory.yml file in YAML format
# Example command line: ansible-inventory --list -i scaleway_inventory.yml

# use hostname as inventory_hostname
# use the private IP address to connect to the host
plugin: scaleway
zones:
  - nl-ams-1
  - fr-par-1
tags:
  - foobar
hostnames:
  - hostname
variables:
  ansible_host: private_ip
  state: state

# use hostname as inventory_hostname and public IP address to connect to the host
plugin: scaleway
hostnames:
  - hostname
zones:
  - fr-par-1
variables:
  ansible_host: public_ip.address

# use exclude tags: select all server except the ones tagged bar OR foo
plugin: scaleway
hostnames:
  - hostname
zones:
  - fr-par-1
exclude_tags:
  - bar
  - foo

# use mandatory_tags: select all server tagged foo AND bar
plugin: scaleway
hostnames:
  - hostname
zones:
  - fr-par-1
mandatory_tags:
  - bar
  - foo

# mix tags and mandatory_tags: select all server tagged foo AND bar AND (alpha OR beta)
# it means we will get the server tagged foo,bar,alpha and foo,bar,beta and foo,bar,alpha,beta but NOT foo,bar
plugin: scaleway
hostnames:
  - hostname
zones:
  - fr-par-1
mandatory_tags:
  - bar
  - foo
tags:
  - alpha
  - beta

# mix tags and exclude_tags: select all server tagged foo OR bar but exclude alpha OR beta
# it means we will get the server tagged foo,bar,omega and foo,bar but NOT foo,bar,alpha NOT bar,beta NOT alpha,beta
plugin: scaleway
hostnames:
  - hostname
zones:
  - fr-par-1
tags:
  - bar
  - foo
exclude_tags:
  - alpha
  - beta

# mix mandatory_tags and exclude_tags: select all server tagged foo AND bar but exclude alpha OR beta
# it means we will get the server tagged foo,bar and foo,bar,omega but NOT foo,bar,alpha NOT foo,bar,beta
plugin: scaleway
hostnames:
  - hostname
zones:
  - fr-par-1
mandatory_tags:
  - bar
  - foo
exclude_tags:
  - alpha
  - beta

# mix all three tags: select all server tagged foo AND bar AND (one OR two) but exclude alpha OR beta
# it means we will get the server tagged foo,bar,one AND foo,bar,two AND foo,bar,one,two but NOT foo,bar NOT foo,bar,one,alpha, NOT foo,one NOT foo,alpha
plugin: scaleway
hostnames:
  - hostname
zones:
  - fr-par-1
mandatory_tags:
  - bar
  - foo
tags:
  - one
  - two
exclude_tags:
  - alpha
  - beta
'''

import json

from ansible.errors import AnsibleError
from ansible.plugins.inventory import BaseInventoryPlugin, Constructable
from ansible_collections.sh4d1.scaleway.plugins.module_utils.scaleway import parse_pagination_link
from ansible.module_utils.urls import open_url
from ansible.module_utils._text import to_native
from ansible.module_utils.six.moves.urllib.parse import urlencode

import ansible.module_utils.six.moves.urllib.parse as urllib_parse


def _fetch_information(token, url, url_suffix):
    results = []
    base_url = url
    paginated_url = url + url_suffix
    while True:
        try:
            print(paginated_url)
            response = open_url(paginated_url,
                                headers={'X-Auth-Token': token,
                                         'Content-type': 'application/json'})
        except Exception as e:
            raise AnsibleError("Error while fetching %s: %s" % (url, to_native(e)))
        try:
            raw_json = json.loads(response.read())
        except ValueError:
            raise AnsibleError("Incorrect JSON payload")

        try:
            results.extend(raw_json["servers"])
        except KeyError:
            raise AnsibleError("Incorrect format from the Scaleway API response")

        link = response.headers['Link']
        if not link:
            return results
        relations = parse_pagination_link(link)
        if 'next' not in relations:
            return results
        paginated_url = base_url + relations['next']


def _build_server_url_suffix(query_string):
    return '/%s?%s' % ("servers", query_string)


def extract_public_ipv4(server_info):
    try:
        return server_info["public_ip"]["address"]
    except (KeyError, TypeError):
        return None


def extract_private_ipv4(server_info):
    try:
        return server_info["private_ip"]
    except (KeyError, TypeError):
        return None


def extract_hostname(server_info):
    try:
        return server_info["hostname"]
    except (KeyError, TypeError):
        return None


def extract_server_id(server_info):
    try:
        return server_info["id"]
    except (KeyError, TypeError):
        return None


def extract_public_ipv6(server_info):
    try:
        return server_info["ipv6"]["address"]
    except (KeyError, TypeError):
        return None


def extract_tags(server_info):
    try:
        return server_info["tags"]
    except (KeyError, TypeError):
        return None


def extract_zone(server_info):
    try:
        return server_info["location"]["zone_id"]
    except (KeyError, TypeError):
        return None


extractors = {
    "public_ipv4": extract_public_ipv4,
    "private_ipv4": extract_private_ipv4,
    "public_ipv6": extract_public_ipv6,
    "hostname": extract_hostname,
    "id": extract_server_id
}


class InventoryModule(BaseInventoryPlugin, Constructable):
    NAME = 'sh4d1.scaleway.scaleway'

    def _fill_host_variables(self, host, server_info):
        targeted_attributes = (
            "arch",
            "commercial_type",
            "id",
            "organization",
            "state",
            "hostname",
        )
        for attribute in targeted_attributes:
            self.inventory.set_variable(host, attribute, server_info[attribute])

        self.inventory.set_variable(host, "tags", server_info["tags"])

        if extract_public_ipv6(server_info=server_info):
            self.inventory.set_variable(host, "public_ipv6", extract_public_ipv6(server_info=server_info))

        if extract_public_ipv4(server_info=server_info):
            self.inventory.set_variable(host, "public_ipv4", extract_public_ipv4(server_info=server_info))

        if extract_private_ipv4(server_info=server_info):
            self.inventory.set_variable(host, "private_ipv4", extract_private_ipv4(server_info=server_info))

    def match_groups(self, server_info, tags, mandatory_tags, exclude_tags):
        server_zone = extract_zone(server_info=server_info)
        server_tags = extract_tags(server_info=server_info)

        # If a server does not have a zone, it means it is archived
        if server_zone is None:
            return set()

        # return empty set if the server have an excluded tag
        if exclude_tags and set(server_tags).intersection(exclude_tags):
            return set()

        # if all the mandatory_tags are not present on the server, return empty
        if mandatory_tags and not set(mandatory_tags).issubset(set(server_tags)):
            return set()
        # if mandatory_tags is None, we assign it the empty set
        elif mandatory_tags is None:
            mandatory_tags = set()

        # If no filtering is defined, all tags are valid groups
        if tags is None:
            return set(server_tags).union((server_zone,))

        # match against given tags
        matching_tags = set(server_tags).intersection(tags)

        if not matching_tags:
            return set()
        else:
            # we just have to add the mandatory_tags
            return matching_tags.union((server_zone,)).union(mandatory_tags).union(server_tags)

    def _filter_host(self, host_infos, hostname_preferences):

        for pref in hostname_preferences:
            if extractors[pref](host_infos):
                return extractors[pref](host_infos)

        return None

    def do_zone_inventory(self, url, url_suffix, token, tags, mandatory_tags, exclude_tags, hostname_preferences):
        raw_zone_hosts_infos = _fetch_information(url=url, url_suffix=url_suffix, token=token)

        for host_infos in raw_zone_hosts_infos:

            hostname = self._filter_host(host_infos=host_infos,
                                         hostname_preferences=hostname_preferences)

            # No suitable hostname were found in the attributes and the host won't be in the inventory
            if not hostname:
                continue

            groups = self.match_groups(host_infos, tags, mandatory_tags, exclude_tags)

            for group in groups:
                self.inventory.add_group(group=group)
                self.inventory.add_host(group=group, host=hostname)
                self._fill_host_variables(host=hostname, server_info=host_infos)

                # Composed variables
                self._set_composite_vars(self.get_option('variables'), host_infos, hostname, strict=False)

    def parse(self, inventory, loader, path, cache=True):
        super(InventoryModule, self).parse(inventory, loader, path)
        self._read_config_data(path=path)

        config_zones = self.get_option("zones")
        tags = self.get_option("tags")
        mandatory_tags = self.get_option("mandatory_tags")
        exclude_tags = self.get_option("exclude_tags")
        token = self.get_option("oauth_token")
        hostname_preference = self.get_option("hostnames")
        organization_id = self.get_option("organization_id")
        query_parameters = ""
        if organization_id is not None:
            query_parameters = urlencode({"organization": organization_id}, doseq=True)

        for zone in set(config_zones):
            self.inventory.add_group(zone)
            api_url = self.get_option("api_url") + '/instance/v1/zones/' + zone
            suffix = _build_server_url_suffix(query_parameters)
            self.do_zone_inventory(url=api_url, url_suffix=suffix, token=token, tags=tags, mandatory_tags=mandatory_tags,
                                   exclude_tags=exclude_tags, hostname_preferences=hostname_preference)
