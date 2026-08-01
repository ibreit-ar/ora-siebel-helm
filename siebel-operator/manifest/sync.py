# !/usr/bin/env python3
"""
Copyright © 2022, 2025, Oracle and/or its affiliates.

$Revision: 1.0.0

Description:
    Operator to make calls for syncing.

Example:

References:

Todos:

CHANGE LOG:
    AUTHOR         DATE          COMMENT
    -------------  ------------  -----------------------------------------------
    Sandeep        01-Jan-2023   Adding Page Documentation
    Samarth        06-Nov-2024   Fixed bug for comp group enablement for server where CG_ENABLE_STATE is enabled ,CG_DISP_ENABLE_STATE is       
                                 disabled and CA_SRVR_ENABLED will be blank

"""

import os
import yaml
import re
import json
import time
import urllib3
import requests
import subprocess
from time import sleep
from shutil import copyfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from ssl import PROTOCOL_TLS_SERVER, SSLContext
import logging
import logging.handlers

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning) # NOQA

namespace = ''

cert_path = '/certs/ca.cert.pem'
k8s_cert_path = '/var/run/secrets/kubernetes.io/serviceaccount/ca.crt'


class Logger:
    def __init__(self):
        self.log_format = f"%(asctime)s - [%(levelname)s] - %(name)s - (%(filename)s)." \
                          f"%(funcName)s(%(lineno)d) - %(message)s"
        self.log_level = os.getenv("LogLevel", "DEBUG")
        self.log_location = os.getenv("LogLocation", "/home/siebel/incremental_changes.log")

    def get_file_handler(self):
        file_handler = logging.handlers.RotatingFileHandler(self.log_location, maxBytes=10485760)
        file_handler.setLevel(self.log_level)
        file_handler.setFormatter(logging.Formatter(self.log_format))
        return file_handler

    def get_stream_handler(self):
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(self.log_level)
        stream_handler.setFormatter(logging.Formatter(self.log_format))
        return stream_handler

    def get_logger(self, name):
        logging.Formatter.converter = time.gmtime
        logger_obj = logging.getLogger(name)
        logger_obj.setLevel(self.log_level)
        logger_obj.addHandler(self.get_file_handler())
        logger_obj.addHandler(self.get_stream_handler())
        return logger_obj


logger = Logger().get_logger(__name__)


class BearerAuth(requests.auth.AuthBase):
    """
    This function forms authorization header
    """
    def __init__(self, token):
        self.token = token

    def __call__(self, r):
        r.headers["authorization"] = "Bearer " + self.token
        return r


class IncrementalChanges:

    def __init__(self):
        self.enterprise_data = None
        self.gateway_data = None
        self.enterprise_name = None
        self.auth_user = None
        self.auth_password = None
        self.comp_restart_list = None
        global namespace
        self.headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
        self.restart_dict = {"enterprise": {}}
        self.yaml_base_path = "/home/siebel/config"
        self.cache_yaml_base_path = "/home/siebel/config/cached"
        self.base_url = "https://smc-0.smc." + namespace + ".svc.cluster.local:4430/siebel/v1.0/cloudgateway"
        # Dynamic urls injected in yaml
        self.inject_dynamic_urls_in_yaml()
        self.load_values()

    @staticmethod
    def get_url(url, server_name=None, enterprise_name=None):
        """
        this function replace server_name with actual server name and enterprise_name with actual enterprise_name
        @param url: url to be replaced
        @param server_name: server name
        @param enterprise_name: name of the enterprise
        @return: replaced url
        """
        try:
            if server_name:
                url = url.replace("server_name", server_name)
            if enterprise_name:
                url = url.replace("enterprise_name", enterprise_name)
            return url
        except Exception as e:
            logger.error(f"IncrementalChanges : get_url : {e}")
            raise e

    @staticmethod
    def get_parameter_url(url, pa_alias):
        """
        Fetch parameter from URL
        @param url: URL from which parameter needs to be created
        @param pa_alias: parameter alias
        @return: str - parametetr url
        """
        try:
            if "?" in url:
                query_params = url.split("?")
                url = query_params[0] + "/" + pa_alias + "?" + query_params[1]
            else:
                url = url + "/" + pa_alias
            return url
        except Exception as e:
            logger.error(f"EnterpriseRuntime : get_parameter_url : ERROR {e}")

    def parameters_comparison(self, parameter_dict, cached_parameter_dict, server_name=None):
        """
        Compares source dict with cached dict parameters and execute only
        newly added or deleted parameters put request
        @param parameter_dict: all parameters
        @param cached_parameter_dict: cached parameters
        @param server_name: server name
        @return: differential parameters
        """
        try:
            change_found = False
            modified_parameters_list = []

            if parameter_dict == cached_parameter_dict:
                logger.debug("Dictionaries are same\n")
                pass
            else:
                # adding parameters
                for item1 in parameter_dict:
                    param_header_found = False
                    modified_parameters = {}
                    for item2 in cached_parameter_dict:
                        if list(item1.keys())[0] == list(item2.keys())[0]:
                            param_header_found = True

                            for (item1_key, value) in item1.items():
                                if item1_key != "url":
                                    for param1 in value:
                                        url = self.get_url(item1["url"], server_name, self.enterprise_name)
                                        key_found = False
                                        api_flag = False

                                        for param2 in item2[item1_key]:
                                            if param1["PA_ALIAS"] == param2["PA_ALIAS"]:
                                                key_found = True
                                                if param1["PA_VALUE"] != param2["PA_VALUE"]:
                                                    api_flag = True
                                                    break
                                        if not key_found:
                                            api_flag = True

                                        if api_flag:
                                            logger.debug("parameters_comparison : Api flag is true\n")
                                            if item1_key not in modified_parameters:
                                                modified_parameters[item1_key] = {}

                                            url = self.get_parameter_url(url, param1["PA_ALIAS"])
                                            modified_parameters["url"] = item1["url"]
                                            modified_parameters[item1_key][param1["PA_ALIAS"]] = param1["PA_VALUE"]

                                            logger.info(
                                                f"parameters_comparison : Modified parameters : \n {modified_parameters}\n")
                                            payload = {"PA_INITVAL": param1["PA_VALUE"]}

                                            logger.debug(
                                                f"parameters_comparison : Calling parameter Put API\n {item1_key} : Url : {url} Payload : {payload}\n")

                                            response = requests.put(url=url,
                                                                    auth=(self.auth_user, self.auth_password),
                                                                    headers=self.headers,
                                                                    data=json.dumps(payload),
                                                                    verify=cert_path)

                                            logger.info(
                                                f"parameters_comparison: Response : {response} : {response.text}\n\n")
                                            change_found = True

                            if modified_parameters:
                                modified_parameters_list.append(modified_parameters)
                    if not param_header_found:
                        for item1_key, value in item1.items():
                            if item1_key != "url":
                                for param in value:
                                    if not item1_key in modified_parameters:
                                        modified_parameters[item1_key] = {}
                                    modified_parameters["url"] = item1["url"]

                                    url = self.get_url(item1["url"], server_name, self.enterprise_name)
                                    url = self.get_parameter_url(url, param["PA_ALIAS"])
                                    payload = {"PA_INITVAL": param["PA_VALUE"]}

                                    response = requests.put(url=url,
                                                            auth=(self.auth_user, self.auth_password),
                                                            headers=self.headers,
                                                            data=json.dumps(payload),
                                                            verify=cert_path)
                                    change_found = True

                                    logger.info(
                                        f"parameters_comparison : payload : {payload} : response: {response} {response.text}\n")

                                    modified_parameters[item1_key].update({param["PA_ALIAS"]: param["PA_VALUE"]})
                        if modified_parameters:
                            modified_parameters_list.append(modified_parameters)

                # deleting parameters
                for item1 in cached_parameter_dict:
                    param_header_found = False
                    modified_parameters = {}
                    for item2 in parameter_dict:
                        if list(item1.keys())[0] == list(item2.keys())[0]:
                            param_header_found = True
                            append_flag = False
                            for (item1_key, value) in item1.items():
                                if item1_key != "url":
                                    for param1 in value:
                                        url = self.get_url(item1["url"], server_name, self.enterprise_name)
                                        key_found = False
                                        for param2 in item2[item1_key]:
                                            if param1["PA_ALIAS"] == param2["PA_ALIAS"]:
                                                key_found = True

                                        if not key_found:
                                            if item1_key not in modified_parameters:
                                                modified_parameters[item1_key] = {}
                                            logger.debug("parameters_comparison : Calling parameter delete API\n")
                                            url = self.get_parameter_url(url, param1["PA_ALIAS"])
                                            url = self.get_url(url, server_name=server_name,
                                                               enterprise_name=self.enterprise_name)
                                            url = url.replace("parameters", "paramoverrides")
                                            logger.info("parameters_comparison: Set parameter value to default \n")
                                            response = requests.delete(url=url,
                                                                       auth=(self.auth_user, self.auth_password),
                                                                       headers=self.headers,
                                                                       verify=cert_path)
                                            modified_parameters[item1_key][param1["PA_ALIAS"]] = param1["PA_VALUE"]

                                            logger.info(
                                                f"parameters_comparison: Response {response} : {response.text}\n\n")
                                            change_found = True

                                            for index, item in enumerate(modified_parameters_list):
                                                for k, v in item.items():
                                                    if k == item1_key:
                                                        modified_parameters_list[index][k].update(
                                                            {param1["PA_ALIAS"]: param1["PA_VALUE"]})
                                                        append_flag = True

                            if not append_flag and modified_parameters:
                                modified_parameters["url"] = item1["url"]
                                modified_parameters_list.append(modified_parameters)
                    if not param_header_found:
                        for item1_key_name, value in item1.items():
                            if item1_key_name != "url":
                                for param in value:
                                    logger.debug("parameters_comparison : Calling parameter delete API\n")
                                    if not item1_key_name in modified_parameters:
                                        modified_parameters[item1_key_name] = {}
                                    modified_parameters["url"] = item1["url"]

                                    url = self.get_url(item1["url"], server_name, self.enterprise_name)
                                    url = self.get_parameter_url(url, param["PA_ALIAS"])
                                    url = url.replace("parameters", "paramoverrides")

                                    logger.info("parameters_comparison: Set parameter value to default \n")

                                    response = requests.delete(
                                        url=url,
                                        auth=(self.auth_user, self.auth_password),
                                        headers=self.headers,
                                        verify=cert_path
                                    )

                                    change_found = True

                                    logger.info(
                                        f"parameters_comparison: Delete Response {response} : {response.text}\n\n")

                                    modified_parameters[item1_key_name].update({param["PA_ALIAS"]: param["PA_VALUE"]})

                        if modified_parameters:
                            modified_parameters_list.append(modified_parameters)

            if change_found:
                logger.debug(f"\nChange found : {change_found}\n")
                logger.debug(f"\n\nModified_parameters_list : \n  {modified_parameters_list}\n")
            return change_found, modified_parameters_list

        except Exception as e:
            logger.error(f"parameters_comparison : Error : {e}")

    def run_all_parameters(self, value, server_name=None):
        """
        Create all parameters
        @param value: parameter value
        @param server_name: server name
        @return: None
        """
        try:
            logger.info("run_all_parameters : Running all parameters\n")
            modified_parameter_list = []

            for item in value:
                modified_parameter = {}
                for item_key, value in item.items():
                    if item_key != "url":
                        modified_parameter[item_key] = {}
                        modified_parameter["url"] = item["url"]
                        for param in value:
                            url = self.get_url(item["url"], server_name, self.enterprise_name)
                            url = self.get_parameter_url(url, param["PA_ALIAS"])
                            payload = {
                                "PA_INITVAL": param["PA_VALUE"]
                            }
                            response = requests.put(
                                url=url,
                                auth=(self.auth_user, self.auth_password),
                                headers=self.headers,
                                data=json.dumps(payload),
                                verify=cert_path
                            )

                            logger.info(f"run_all_parameters : payload : {payload} : response: {response} {response.text}\n")

                            modified_parameter[item_key].update({
                                param["PA_ALIAS"]: param["PA_VALUE"]
                            })

                if modified_parameter[item_key]:
                    modified_parameter_list.append(modified_parameter)

            return modified_parameter_list
        except Exception as e:
            logger.error(f"parameters_comparison : Error : {e}")

    @staticmethod
    def parse_yaml_string(path):
        """
        Read the path and parse it as YAML
        @param path: path where content is present
        @return: dict - parsed content as dictionary
        todo - avoid using yaml.safe_load twice
        """
        """ Parses yaml files """
        try:
            with open(path, 'r') as stream:
                try:
                    parsed_yaml = yaml.safe_load(stream)
                    try:
                        parsed_yaml = yaml.safe_load(parsed_yaml)
                    except Exception as e:
                        pass
                    return parsed_yaml

                except yaml.YAMLError as e:
                    logger.error(e)
                    return None

        except Exception as e:
            logger.error(f"Config : parse_yaml_string : ERROR : {e}")

    def load_values(self):
        """
        Method to set values in the class instance variables
        @return: None
        """
        try:
            logger.debug("load_values\n")
            enterprise_yaml = self.yaml_base_path + "/enterprise.yaml"
            gateway_yaml = self.yaml_base_path + "/gateway.yaml"

            self.enterprise_data = self.parse_yaml_string(enterprise_yaml)
            self.gateway_data = self.parse_yaml_string(gateway_yaml)
            self.enterprise_name = self.enterprise_data["enterprise"]["EnterpriseDeployment"]["enterprise_deployment_info"][0]["EnterpriseDeployParams"]["SiebelEnterprise"]
            self.auth_user = self.gateway_data["gateway"]["SecurityProfiles"]["profiles"][0]["SecurityConfigParams"]["TestUserName"]
            self.auth_password = self.gateway_data["gateway"]["SecurityProfiles"]["profiles"][0]["SecurityConfigParams"]["TestUserPwd"]

            logger.debug(f"\nload_values : Enterprise_name : {self.enterprise_name}\n")
        except Exception as e:
            logger.error(f"load_values : Error : {e}")

    @staticmethod
    def add_reference_urls(yaml_file, yaml_dict):
        """
         Adds REST API 'url' fields to specific sections of Siebel YAML config files.

        This function examines the type of YAML file (for example, server, enterprise,
        or gateway) based on its filename, and then inserts URL fields at key places
        in the data (like parameters, component groups, profiles, etc).

        The URLs use placeholders (such as "enterprise_name" or "server_name") to
        be filled in later

        Args:
            yaml_file (str): The name of the YAML file.
            yaml_dict (dict): The YAML data loaded into a dictionary. This will be changed in-place.

        """
        base_url = f"https://smc-0.smc.{namespace}.svc.cluster.local:4430/siebel/v1.0/cloudgateway"
        param_type_url_suffix = {
            "basic_params": "",
            "hidden_params": "?hidden=true",
            "advanced_params": "?advanced=true"
        }

        def assign_param_block_urls(blocks, url_template):
            if not isinstance(blocks, list):
                return
            for pb in blocks:
                for param_type, suffix in param_type_url_suffix.items():
                    if param_type in pb:
                        pb["url"] = url_template + suffix
                        break

        # 1. server_*.yaml
        def handle_server():
            server_keys = [key for key in yaml_dict if key.startswith('server_')]
            d = yaml_dict[server_keys[0]] if server_keys else yaml_dict

            assign_param_block_urls(
                d.get("parameters"),
                f"{base_url}/enterprises/enterprise_name/servers/server_name/parameters"
            )
            if "profiles" in d:
                d["profiles"]["url"] = f"{base_url}/profiles/servers"
            for cg_name, cg in (d.get("component_groups") or {}).items():
                cg_base = f"{base_url}/enterprises/enterprise_name/compgroups/{cg_name}"
                cg["url"] = cg_base

                # Safe: if the group has parameter blocks, assign block URLs with proper suffixes
                assign_param_block_urls(
                    cg.get("parameters"),
                    f"{cg_base}/parameters"
                )

                for comp_name, comp in cg.get("components", {}).items():
                    comp_url = f"{base_url}/enterprises/enterprise_name/servers/server_name/components/{comp_name}"
                    comp["url"] = comp_url
                    assign_param_block_urls(
                        comp.get("parameters"),
                        f"{comp_url}/parameters"
                    )

        # 2. comp_definitions.yaml
        def handle_comp_definitions():
            # Component definitions: component-level URL + param blocks
            for comp_name, comp_data in yaml_dict.get("component_definitions", {}).items():
                comp_base = f"{base_url}/enterprises/enterprise_name/compdefs/{comp_name}"
                comp_data["url"] = comp_base
                assign_param_block_urls(
                    comp_data.get("parameters"),
                    f"{comp_base}/parameters"
                )

            # Component groups: group-level URL + param blocks (if present)
            for cg_name, cg_data in yaml_dict.get("component_groups", {}).items():
                cg_base = f"{base_url}/enterprises/enterprise_name/compgroups/{cg_name}"
                cg_data["url"] = cg_base
                assign_param_block_urls(
                    cg_data.get("parameters"),
                    f"{cg_base}/parameters"
                )

        # 3. enterprise.yaml
        def handle_enterprise():
            ed = yaml_dict["enterprise"]
            section_url = {
                "EnterpriseDeployment": f"{base_url}/deployments/enterprises",
                "EnterpriseProfiles": f"{base_url}/profiles/enterprises"
            }
            for section, url in section_url.items():
                if section in ed:
                    ed[section]["url"] = url  # << This should create 'url' field at EnterpriseProfiles level
            assign_param_block_urls(
                ed.get("parameters"),
                f"{base_url}/enterprises/enterprise_name/parameters"
            )

        # 4. gateway.yaml
        def handle_gateway():
            g = yaml_dict["gateway"]
            gateway_section_urls = {
                "BootstrapCG": f"{base_url}/bootstrapCG",
                "CGinfo": f"https://smc-0.smc.{namespace}.svc.cluster.local:4430/siebel/v1.0/cginfo",
                "GatewayClusterDeployment": f"{base_url}/deployments/gatewaycluster",
                "GatewayClusterProfiles": f"{base_url}/profiles/gatewaycluster",
                "HeartBeat": f"{base_url}/heartbeat",
                "SecurityProfiles": f"{base_url}/GatewaySecurityProfile"
            }
            # Ensure HeartBeat block is always present
            if "HeartBeat" not in g:
                g["HeartBeat"] = {}
            for section, url in gateway_section_urls.items():
                if section in g:
                    g[section]["url"] = url

        # 5. migration.yaml
        def handle_migration():
            m = yaml_dict["migration"]
            migration_section_urls = {
                "MigrationDeployment": f"{base_url}/deployments/migrations",
                "MigrationProfiles": f"{base_url}/profiles/migrations"
            }
            for section, url in migration_section_urls.items():
                if section in m:
                    m[section]["url"] = url

        # 6. named_subsystem.yaml
        def handle_named_subsystem():
            ns = yaml_dict["named_subsystem"]
            for ns_name, ns_data in ns.items():
                assign_param_block_urls(
                    ns_data.get("parameters"),
                    f"{base_url}/enterprises/enterprise_name/namedsubsystems/{ns_name}/parameters"
                )

        # 7. sai_quantum.yaml
        def handle_sai_quantum():
            for key in yaml_dict:
                if key.startswith("sai_"):
                    yaml_dict[key]["url"] = f"{base_url}/profiles/swsm"

        # File type dispatcher
        basename = os.path.basename(yaml_file)
        handler_patterns = [
            (r"^server_.*\.yaml$", handle_server),
            (r"^comp_definitions\.yaml$", handle_comp_definitions),
            (r"^enterprise\.yaml$", handle_enterprise),
            (r"^gateway\.yaml$", handle_gateway),
            (r"^migration\.yaml$", handle_migration),
            (r"^named_subsystem\.yaml$", handle_named_subsystem),
            (r"^sai_.*\.yaml$", handle_sai_quantum),
        ]
        for pattern, handler in handler_patterns:
            if re.match(pattern, basename):
                handler()
                break
        else:
            if not re.match(r"^(differences|enabledcomps)\.yaml$", basename):
                logger.warning(f"No handler found for file: {yaml_file}")

    def inject_dynamic_urls_in_yaml(self):
        """
        Injects dynamic 'url' fields into Siebel YAML configuration files
        according to their structure and then writes the updated files back.

        This method performs the following steps:
            1. Loads a YAML file from location into a Python dictionary.
            2. Injects context-aware dynamic reference URLs into the correct sections of
               the files, using standard blueprint logic defined in `self.add_reference_urls`.
            3. Saves the modified fields, now containing the injected URLs,
               back to the original YAML file location (and the corresponding cached location if present).
        """
        files = [
            f for f in os.listdir(self.yaml_base_path)
            if os.path.isfile(os.path.join(self.yaml_base_path, f))
        ]
        for fname in files:
            if fname.endswith(".yaml"):
                yaml_file = os.path.join(self.yaml_base_path, fname)
                # cached_yaml = os.path.join(self.cache_yaml_base_path, "cached_" + fname)
                yaml_dict = self.parse_yaml_string(yaml_file)

                # Inject URLs and write back
                self.add_reference_urls(yaml_file, yaml_dict)
                with open(yaml_file, "w") as f:
                    yaml.dump(yaml_dict, f, default_flow_style=False, sort_keys=False)

                # if os.path.exists(cached_yaml):
                #     cached_dict = incremental.parse_yaml_string(cached_yaml)
                #     self.add_reference_urls(cached_yaml, cached_dict)
                #     with open(cached_yaml, "w") as f:
                #         yaml.dump(cached_dict, f, default_flow_style=False, sort_keys=False)

    @staticmethod
    def get_replicas(sts_name):
        """
        Get the no of replica for a Stateful set
        @param sts_name: name of the stateful set
        @return: stdout - raw output PIPE
        """
        try:
            command = "kubectl get sts {} -n {} ".format(sts_name, namespace) + "-o=jsonpath='{.status.replicas}'"
            response = subprocess.check_output(command, shell=True, encoding='utf8').strip()
            return response
        except Exception as e:
            logger.error(f"get_replicas : Error {e}")

    @staticmethod
    def restart_server(server_name, server_namespace):
        """
        Restart the siebel server
        @param server_name: name of the server
        @param server_namespace: namespace of the server
        @return: None
        """
        logger.info(f"Restarting server {server_name}\n")
        command = 'kubectl exec {} -n {} -- bash -c "source /home/siebel/.bash_profile;stop_server all;start_server all"'.format(server_name, server_namespace)
        response = subprocess.Popen(
            command,
            shell=True,
            encoding='utf8',
            stdin=None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        logger.debug(response)

    def enterprise_runtime(self):
        """
        Fetch the enterprise run time values
        @return: None
        """
        try:
            yaml_file = self.yaml_base_path + "/enterprise.yaml"
            cached_yaml = self.cache_yaml_base_path + "/cached_enterprise.yaml"

            enterprise_dict = self.parse_yaml_string(yaml_file)

            # First time run - create only cached file/cm
            if not os.path.exists(cached_yaml):
                copyfile(yaml_file, cached_yaml)
                logger.info("No cache yaml found")

            else:
                cached_enterprise_dict = self.parse_yaml_string(cached_yaml)

                if "enterprise" in enterprise_dict:
                    if "parameters" in enterprise_dict["enterprise"]:
                        parameter_dict = enterprise_dict["enterprise"]["parameters"]
                        cached_parameter_dict = cached_enterprise_dict["enterprise"]["parameters"]

                        logger.debug("enterprise_runtime : Enterprise parameter comparison")

                        flag, parameters = self.parameters_comparison(parameter_dict, cached_parameter_dict)
                        if flag:
                            self.restart_dict["enterprise"]["parameters"] = parameters

                copyfile(yaml_file, cached_yaml)
        except Exception as e:
            logger.error(f"enterprise_runtime : Error {e}")

    def named_subsystem_runtime(self):
        """
        Create Named Sub system
        @return: None
        """
        # try:
        logger.debug("named_subsystem_runtime\n")
        yaml_file = self.yaml_base_path + "/named_subsystem.yaml"
        cached_yaml = self.cache_yaml_base_path + "/cached_named_subsystem.yaml"

        named_subsystem_dict = self.parse_yaml_string(yaml_file)

        # First time run
        if not os.path.exists(cached_yaml):
            copyfile(yaml_file, cached_yaml)
        else:
            cached_subsystem_dict = self.parse_yaml_string(cached_yaml)
            if "named_subsystem" in named_subsystem_dict:
                self.restart_dict["enterprise"]["named_subsystem"] = {}
                data = named_subsystem_dict['named_subsystem']
                cached_data = cached_subsystem_dict['named_subsystem']

                # Adding new subsystem
                for data_key, value in data.items():
                    api_flag = False

                    if "definition" in value:
                        if data_key not in cached_data:
                            api_flag = True

                        if api_flag:
                            # no restart required
                            url = self.get_url(value["url"], enterprise_name=self.enterprise_name)

                            # Validation
                            logger.info(f"Validating if {data_key} named subsystem is already preset\n")

                            response = requests.get(
                                url=url,
                                auth=(self.auth_user, self.auth_password),
                                headers=self.headers,
                                verify=cert_path
                            )
                            logger.info(f"Response of validation: {response}{response.text}\n")

                            post_api_flag = False

                            re = json.loads(response.text)
                            if "Result" in re:
                                if not re["Result"]:
                                    post_api_flag = True

                            if post_api_flag or response.status_code != 200:
                                logger.info(f"Applying POST request to create {data_key} named subsystem\n")
                                payload = value["definition"]

                                url_params = url.split("/")
                                url = "/".join(url_params[:-1])

                                # Run POST api
                                response = requests.post(
                                    url=url,
                                    auth=(self.auth_user, self.auth_password),
                                    headers=self.headers,
                                    data=json.dumps(payload),
                                    verify=cert_path
                                )

                                logger.info(f"Response of POST request: {response} {response.text}\n")

                                if response.status_code == 200:
                                    logger.info(f"Named subsystem {data_key} created successful\n")

                                    if data_key not in self.restart_dict["enterprise"]["named_subsystem"]:
                                        self.restart_dict["enterprise"]["named_subsystem"][data_key] = {}
                                    self.restart_dict["enterprise"]["named_subsystem"][data_key]["definition"] = payload

                    if "parameters" in value:
                        parameter_dict = value["parameters"]
                        if data_key in cached_subsystem_dict["named_subsystem"]:
                            cached_parameter_dict = cached_subsystem_dict["named_subsystem"][data_key]["parameters"]

                            logger.debug(f"named_subsystem_runtime : Comparing {data_key} named subsystem parameters\n")

                            flag, parameters = self.parameters_comparison(parameter_dict, cached_parameter_dict)
                            if flag:
                                if data_key not in self.restart_dict["enterprise"]["named_subsystem"]:
                                    self.restart_dict["enterprise"]["named_subsystem"][data_key] = {}
                                self.restart_dict["enterprise"]["named_subsystem"][data_key]["parameters"] = parameters
                        else:
                            logger.info(f"Applying all parameter for new named subsystem {data_key}")

                            parameters = self.run_all_parameters(parameter_dict)
                            if data_key not in self.restart_dict["enterprise"]["named_subsystem"]:
                                self.restart_dict["enterprise"]["named_subsystem"][data_key] = {}

                            self.restart_dict["enterprise"]["named_subsystem"][data_key]["parameters"] = parameters

                # Deleting subsystem
                for cached_data_key, value in cached_data.items():
                    if "definition" in value:
                        if cached_data_key in data:
                            pass

                        else:
                            logger.info(f"Delete named subsystem {cached_data_key}")
                            logger.info(f"Validating if named subsystem {cached_data_key} is present\n")
                            # Run delete api
                            url = self.get_url(
                                url=value["url"],
                                enterprise_name=self.enterprise_name
                            )
                            response = requests.get(
                                url=url,
                                auth=(self.auth_user, self.auth_password),
                                headers=self.headers,
                                verify=cert_path
                            )
                            re = json.loads(response.text)
                            logger.info(re)
                            if response.status_code == 200 and "Result" in re:
                                if re["Result"]:
                                    # Run delete api
                                    logger.info(f"Applying POST request to delete {cached_data_key} named subsystem\n")
                                    response = requests.delete(
                                        url=url,
                                        auth=(self.auth_user, self.auth_password),
                                        headers=self.headers,
                                        verify=cert_path
                                    )

                                    if response.status_code == 200:

                                        logger.info(f"Named subsystem {cached_data_key} is deleted successfully \n")
                                        if cached_data_key not in self.restart_dict["enterprise"]["named_subsystem"]:
                                            self.restart_dict["enterprise"]["named_subsystem"][cached_data_key] = {}
                                        self.restart_dict["enterprise"]["named_subsystem"][cached_data_key]["definition"] = {}

                copyfile(yaml_file, cached_yaml)
        # except Exception as e:
        #     logger.error(e)

    def comp_defs_runtime(self):
        """
        Component definitions run time calls
        @return: None
        """
        yaml_file = self.yaml_base_path + "/comp_definitions.yaml"
        cached_yaml = self.cache_yaml_base_path + "/cached_comp_definitions.yaml"

        comp_defs_yaml = self.parse_yaml_string(yaml_file)

        # First time run
        if not os.path.exists(cached_yaml):
            copyfile(yaml_file, cached_yaml)

        else:
            cached_comp_defs_yaml = self.parse_yaml_string(cached_yaml)

            if "component_definitions" in comp_defs_yaml:
                if "component_definitions" not in self.restart_dict["enterprise"]:
                    self.restart_dict["enterprise"]["component_definitions"] = {}

                # Adding new comp def
                for (comp_def_key, value) in comp_defs_yaml["component_definitions"].items():
                    api_flag = False
                    cached_data = cached_comp_defs_yaml["component_definitions"]

                    if "definition" in value:
                        if comp_def_key not in cached_data:
                            api_flag = True

                        if api_flag:
                            # no restart required since it is comp def
                            logger.info(f"New comp def {comp_def_key} identified\n")
                            logger.info(f"Validating comp definition {comp_def_key}")
                            # validation
                            url = self.get_url(value["url"], enterprise_name=self.enterprise_name)

                            response = requests.get(url=url,
                                                    auth=(self.auth_user, self.auth_password),
                                                    headers=self.headers,
                                                    verify=cert_path)

                            logger.info(f"Response of validation : {response}{response.text}\n")

                            re = json.loads(response.text)
                            logger.info(re)
                            if response.status_code == 200 and "Result" in re:
                                if not re["Result"]:
                                    logger.info(f"Creating comp def {comp_def_key} using POST API\n")
                                    # Run POST api

                                    # url = "https://129.213.124.55:31804/siebel/v1.0/cloudgateway/enterprises/siebel/compdefs"
                                    # payload = {
                                    #             CC_ALIAS: "test"
                                    #             CC_DESC_TEXT: "test"
                                    #             CC_DISP_ENABLE_ST: ""
                                    #             CC_ENABLE_STATE: ""
                                    #             CC_NAME: "test"
                                    #             CC_RUNMODE: "Batch"
                                    #             CG_ALIAS: "AsgnMgmt"
                                    #             CG_NAME: "AsgnMgmt"
                                    #             CT_ALIAS: "CalDAV Service"
                                    #             CT_NAME: "CalDAV Service"
                                    #           }

                                    payload = value["definition"]

                                    url_params = url.split("/")
                                    url = "/".join(url_params[:-1])

                                    response = requests.post(url=url,
                                                             auth=(self.auth_user,
                                                                   self.auth_password),
                                                             headers=self.headers,
                                                             data=json.dumps(payload),
                                                             verify=cert_path)

                                    logger.info(f"Response of POST api: {response} : {response.text}\n")

                                    if response.status_code == 200:
                                        logger.info(f"Comp def {comp_def_key} Created successfully")
                                        if comp_def_key not in self.restart_dict["enterprise"]["component_definitions"]:
                                            self.restart_dict["enterprise"]["component_definitions"][comp_def_key] = {}

                                        # Activate
                                        # url = https://slc02hyd.us.oracle.com:16691/oracle-crm/v1.0/cloudgateway/enterprises/siebel/compdefs/test

                                        url = self.get_url(value["url"], enterprise_name=self.enterprise_name)
                                        payload = {"Action": "activate"}
                                        logger.info(payload)

                                        response = requests.post(
                                            url=url,
                                            auth=(self.auth_user, self.auth_password),
                                            headers=self.headers,
                                            data=json.dumps(payload),
                                            verify=cert_path
                                        )

                                        logger.info(f"{response}{response.text}")
                                        if response.status_code == 200:
                                            logger.info("Activated\n")
                                            self.restart_dict["enterprise"]["component_definitions"][comp_def_key]["definition"] = payload

                    if "parameters" in value:
                        parameter_dict = value["parameters"]

                        if comp_def_key in cached_comp_defs_yaml["component_definitions"]:
                            cached_parameter_dict = cached_comp_defs_yaml["component_definitions"][comp_def_key]["parameters"]
                            logger.debug(f"comp_defs_runtime : Comparing parameters  of comp def {comp_def_key}")

                            flag, parameters = self.parameters_comparison(parameter_dict, cached_parameter_dict)
                            if flag:
                                if comp_def_key not in self.restart_dict["enterprise"]["component_definitions"]:
                                    self.restart_dict["enterprise"]["component_definitions"][comp_def_key] = {}
                                self.restart_dict["enterprise"]["component_definitions"][comp_def_key]["parameters"] = parameters
                        else:
                            logger.info(f"comp_defs_runtime : Running all parameters for comp def {comp_def_key}\n")
                            parameters = self.run_all_parameters(parameter_dict)
                            if comp_def_key not in self.restart_dict["enterprise"]["component_definitions"]:
                                self.restart_dict["enterprise"]["component_definitions"][comp_def_key] = {}
                            self.restart_dict["enterprise"]["component_definitions"][comp_def_key]["parameters"] = parameters

                # Delete comp def
                for (cached_comp_def_key, value) in cached_comp_defs_yaml["component_definitions"].items():
                    data = comp_defs_yaml["component_definitions"]

                    if "definition" in value:
                        if cached_comp_def_key in data:
                            pass

                        else:
                            logger.info(f"Delete comp def {cached_comp_def_key}")

                            # Deactivate
                            url = self.get_url(value["url"], enterprise_name=self.enterprise_name)

                            payload = {"Action": "deactivate"}
                            logger.info(f"Step 1 : {payload}\n")
                            response = requests.post(url=url,
                                                     auth=(self.auth_user, self.auth_password),
                                                     headers=self.headers,
                                                     data=json.dumps(payload),
                                                     verify=cert_path)

                            logger.info(f"Response : {response}{response.text}")
                            # delete API
                            logger.info(f"Step 2 : Deleting comp definition {cached_comp_def_key} using POST API ")
                            response = requests.delete(
                                url=url,
                                auth=(self.auth_user, self.auth_password),
                                headers=self.headers,
                                verify=cert_path
                            )

                            logger.info(f" Response of POST API {response}{response.text}\n")
                            if response.status_code == 200:
                                if cached_comp_def_key not in self.restart_dict["enterprise"]["component_definitions"]:
                                    self.restart_dict["enterprise"]["component_definitions"][cached_comp_def_key] = {}
                                self.restart_dict["enterprise"]["component_definitions"][cached_comp_def_key]["definition"] = {}

                if "component_groups" in comp_defs_yaml:
                    if "component_groups" not in self.restart_dict["enterprise"]:
                        self.restart_dict["enterprise"]["component_groups"] = {}

                    # Adding new comp group
                    for comp_def_comp_group_key, value in comp_defs_yaml["component_groups"].items():
                        if "definition" in value:
                            api_flag = False
                            cached_data = cached_comp_defs_yaml["component_groups"]
                            if comp_def_comp_group_key not in cached_data:
                                api_flag = True
                            if api_flag:
                                logger.info(f"New comp group def {comp_def_comp_group_key} identified\n")
                                # Validation
                                logger.info(f"Validating if comp group {comp_def_comp_group_key} present\n")

                                # url = "https://129.213.124.55:30188/siebel/v1.0/cloudgateway/enterprises/siebel/servers/lily-0/compgroups/" + key
                                url = self.get_url(value["url"], enterprise_name=self.enterprise_name)

                                response = requests.get(url=url,
                                                        auth=(self.auth_user, self.auth_password),
                                                        headers=self.headers,
                                                        verify=cert_path)
                                re = json.loads(response.text)
                                logger.info(f"Response of validation{response}{response.text}\n")

                                if response.status_code == 200 and "Result" in re:
                                    if not re["Result"]:
                                        url_params = value["url"].split("/")
                                        url = "/".join(url_params[:-1])
                                        url = self.get_url(url, enterprise_name=self.enterprise_name)
                                        payload = value["definition"]

                                        logger.info(f"Creating comp group {comp_def_comp_group_key} present\n")
                                        response = requests.post(url=url,
                                                                 auth=(self.auth_user, self.auth_password),
                                                                 headers=self.headers,
                                                                 data=json.dumps(payload),
                                                                 verify=cert_path)

                                        logger.info(f"{response}{response.text}")

                                        if response.status_code == 200:
                                            logger.info(f"Comp group {comp_def_comp_group_key} created\n")
                                            if comp_def_comp_group_key not in self.restart_dict["enterprise"]["component_groups"]:
                                                self.restart_dict["enterprise"]["component_groups"][comp_def_comp_group_key] = {}

                                            self.restart_dict["enterprise"]["component_groups"][comp_def_comp_group_key]["definition"] = payload

                    # Deleting new comp group
                    for cached_comp_def_key_name, value in cached_comp_defs_yaml["component_groups"].items():
                        if "definition" in value:
                            data = comp_defs_yaml["component_groups"]
                            if "definition" in value:
                                if cached_comp_def_key_name in data:
                                    pass

                                else:
                                    logger.info(f"Delete comp group def {cached_comp_def_key_name} identified\n")
                                    # url = "https://129.213.124.55:30188/siebel/v1.0/cloudgateway/enterprises/siebel/servers/lily-0/compgroups/" + key
                                    url = self.get_url(value["url"], enterprise_name=self.enterprise_name)
                                    payload = {
                                        "Action": "disable"
                                    }

                                    logger.info(f"Step 1 : {payload}")

                                    response = requests.post(
                                        url=url,
                                        auth=(self.auth_user, self.auth_password),
                                        headers=self.headers,
                                        data=json.dumps(payload),
                                        verify=cert_path
                                    )

                                    logger.info(f" Response {response}{response.text}\n")

                                    logger.info(f"Step 2 : Delete comp group using delete api\n")
                                    response = requests.delete(url=url,
                                                               auth=(self.auth_user, self.auth_password),
                                                               headers=self.headers,
                                                               verify=cert_path)
                                    logger.info(f"{response}{response.text}")

                                    if response.status_code == 200:
                                        logger.info("Deleted comp group {key} successfully\n")

                                        if cached_comp_def_key_name not in self.restart_dict["enterprise"]["component_groups"]:
                                            self.restart_dict["enterprise"]["component_groups"][cached_comp_def_key_name] = {}

                                        self.restart_dict["enterprise"]["component_groups"][cached_comp_def_key_name]["definition"] = {}
            copyfile(yaml_file, cached_yaml)

    def sai_scs_runtime(self):
        """
        Siebel AI run time calls for SCS arch
        @return: None
        """
        logger.debug("sai_scs_runtime")
        self.restart_dict["enterprise"]["sai_profile"] = False
        files = [f for f in os.listdir(self.yaml_base_path) if os.path.isfile(os.path.join(self.yaml_base_path, f))]
        for fname in files:
            if "aiprofile" in fname:
                json_file = self.yaml_base_path + "/" + fname
                cached_json_file = self.cache_yaml_base_path + "/cached_" + fname

                # First time run
                if not os.path.exists(cached_json_file):
                    logger.debug("Cached yaml doesnt exist\n")
                    copyfile(json_file, cached_json_file)
                else:
                    json_data = self.parse_yaml_string(json_file)
                    cached_json_data = self.parse_yaml_string(cached_json_file)

                    if json_data != cached_json_data:
                        logger.debug("Change identified in file aiprofile.json ")
                        self.restart_dict["enterprise"]["sai_profile"] = True

                    copyfile(json_file, cached_json_file)

    def sai_crm_runtime(self):
        """
        Siebel AI run time calls for CRM arch
        @return: None
        """
        logger.debug("sai_crm_runtime\n")
        files = [f for f in os.listdir(self.yaml_base_path) if os.path.isfile(os.path.join(self.yaml_base_path, f))]
        for fname in files:
            if "sai" in fname.split("/")[-1]:
                sts_name = fname.split("/")[-1].split("_")[-1].split(".")[0]
                logger.info(f"sai stateful set name : {sts_name}")

                yaml_file = self.yaml_base_path + "/" + fname
                cached_yaml = self.cache_yaml_base_path + "/cached_" + fname

                sai_dict = self.parse_yaml_string(yaml_file)
                parent_node = "sai_" + sts_name

                if sts_name == "siebms":
                    pass
                else:
                    if not os.path.exists(cached_yaml):
                        logger.debug("Sai Cached yaml doesnt exist\n")
                        copyfile(yaml_file, cached_yaml)
                    else:
                        cached_sai_dict = self.parse_yaml_string(cached_yaml)
                        if sai_dict == cached_sai_dict:
                            logger.debug(f"No change in sai profile {sts_name}")
                            pass
                        else:
                            logger.debug("Sai profile update")
                            sai_profile = sai_dict[parent_node]["profiles"][0]["Profile"]["ProfileName"]

                            url = sai_dict[parent_node]["url"] + "/" + sai_profile
                            payload = sai_dict[parent_node]["profiles"][0]

                            logger.info(f"Updating sai profile for server for sai")

                            response = requests.put(url=url,
                                                    auth=(self.auth_user, self.auth_password),
                                                    headers=self.headers,
                                                    data=json.dumps(payload),
                                                    verify=cert_path)
                            logger.info(f"{url} {response} : {response.text}\n")

                        copyfile(yaml_file, cached_yaml)

    def server_runtime(self):
        """
        Server run time calls
        @return: None
        """
        global namespace

        self.restart_dict["enterprise"]["siebserver"] = {}

        files = [f for f in os.listdir(self.yaml_base_path) if os.path.isfile(os.path.join(self.yaml_base_path, f))]
        for fname in files:
            if "server" in fname.split("/")[-1]:
                sts_name = fname.split("/")[-1].split("_")[-1].split(".")[0]
                logger.info(f"server stateful set name : {sts_name}")

                yaml_file = self.yaml_base_path + "/" + fname
                cached_yaml = self.cache_yaml_base_path + "/cached_" + fname

                server_dict = self.parse_yaml_string(yaml_file)
                parent_node = "server_" + sts_name

                if sts_name == "siebms":
                    replicas = 1
                else:
                    replicas = self.get_replicas(sts_name)
                    if replicas:
                        replicas = int(replicas)
                    else:
                        replicas = server_dict[parent_node]["replicas"]

                # First time run
                if not os.path.exists(cached_yaml):
                    logger.debug("Cached yaml doesnt exist\n")
                    copyfile(yaml_file, cached_yaml)

                    self.restart_dict["enterprise"]["siebserver"] = {}
                    for i in range(replicas):
                        if sts_name == "siebms":
                            server_name = "siebms"
                        else:
                            server_name = sts_name + "-" + str(i)

                        self.restart_dict["enterprise"]["siebserver"].update({server_name: {}})
                else:
                    cached_server_dict = self.parse_yaml_string(cached_yaml)

                    if parent_node in server_dict:
                        for i in range(replicas):
                            if sts_name == "siebms":
                                server_name = "siebms"
                            else:
                                server_name = sts_name + "-" + str(i)

                            if server_name not in self.restart_dict["enterprise"]["siebserver"]:
                                self.restart_dict["enterprise"]["siebserver"][server_name] = {}
                                self.restart_dict["enterprise"]["siebserver"][server_name]["url"] = self.base_url + "/enterprises/" + self.enterprise_name + "/servers/" + server_name

                            if "parameters" in server_dict[parent_node]:
                                parameter_dict = server_dict[parent_node]["parameters"]
                                cached_parameter_dict = cached_server_dict[parent_node]["parameters"]

                                logger.debug(f"Server {parent_node} parameter comparison")

                                flag, parameters = self.parameters_comparison(parameter_dict, cached_parameter_dict, server_name=server_name)
                                if flag:
                                    self.restart_dict["enterprise"]["siebserver"][server_name]["parameters"] = parameters

                            if "component_groups" in server_dict[parent_node]:
                                # Adding new component group
                                self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"] = {}
                                for parent_cg_key, value in server_dict[parent_node]["component_groups"].items():
                                    self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][parent_cg_key] = {}
                                    self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][parent_cg_key]["url"] = value["url"]

                                    # new component group in incremental change
                                    if parent_cg_key not in cached_server_dict[parent_node]["component_groups"]:

                                        logger.info(f"New comp group {parent_cg_key} addition identified for server {server_name}\n")
                                        # Enable component group
                                        url = value["url"].replace("compgroups", "servers/server_name/compgroups")
                                        url = self.get_url(url, server_name, self.enterprise_name)
                                        # Validation
                                        logger.info(f"Validating component group {parent_cg_key}")
                                        response = requests.get(
                                            url=url,
                                            auth=(self.auth_user, self.auth_password),
                                            headers=self.headers,
                                            verify=cert_path
                                        )
                                        logger.info(f"{response}{response.text}")
                                        if response.status_code == 200:
                                            re = json.loads(response.text)
                                            if "Result" in re:
                                                if re["Result"]:
                                                    if re["Result"][0]["CA_ASSIGNED"] == "N":
                                                        logger.info(f"Assigning component group {parent_cg_key} to server")
                                                        payload = {"Action": "assign"}
                                                        response = requests.post(
                                                            url=url,
                                                            auth=(self.auth_user, self.auth_password),
                                                            headers=self.headers,
                                                            data=json.dumps(payload),
                                                            verify=cert_path
                                                        )
                                                        logger.info(f"Response : {response} {response.text}\n")

                                                        payload = {"Action": "enable"}

                                                        logger.info(f"Enable component group {parent_cg_key} , {url} : {payload}")

                                                        response = requests.post(url=url,
                                                                                 auth=(self.auth_user,
                                                                                       self.auth_password),
                                                                                 headers=self.headers,
                                                                                 data=json.dumps(payload),
                                                                                 verify=cert_path)

                                                        logger.info(f"Response : {response} {response.text}\n")

                                                    elif re["Result"][0]["CG_ENABLE_STATE"] != "Enabled" or re["Result"][0]["CA_SRVR_ENABLED"] != "Y":
                                                        payload = {
                                                            "Action": "enable"
                                                        }

                                                        logger.info(f"Enable component group {parent_cg_key} , {url} : {payload}")

                                                        response = requests.post(
                                                            url=url,
                                                            auth=(self.auth_user, self.auth_password),
                                                            headers=self.headers,
                                                            data=json.dumps(payload),
                                                            verify=cert_path
                                                        )

                                                        logger.info(f"Response : {response} {response.text}\n")

                                                        if response.status_code == 200:
                                                            logger.info(f"Component group {parent_cg_key} enabled successfully\n")
                                                            self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][parent_cg_key]["definition"] = payload

                                                    else:
                                                        logger.info(f"Component group : {parent_cg_key} is already enabled\n")
                                                    # Disable components
                                                    component_list = server_dict[parent_node]["component_groups"][parent_cg_key]["components"].keys()

                                                    url = self.get_url(value["url"], server_name, self.enterprise_name) + "/compdefs"
                                                    logger.debug(component_list)
                                                    logger.debug(url)
                                                    response = requests.get(url=url,
                                                                            auth=(self.auth_user, self.auth_password),
                                                                            headers=self.headers,
                                                                            verify=cert_path)
                                                    logger.info(f"Response: {response}{response.text}\n")

                                                    if response.status_code == 200:
                                                        re = json.loads(response.text)
                                                        if "Result" in re:
                                                            if re["Result"]:
                                                                for item in re["Result"]:
                                                                    comp_name = item["CC_ALIAS"]
                                                                    if comp_name in component_list:
                                                                        pass
                                                                    else:
                                                                        url_param = value["url"].split("/")
                                                                        url = "/".join(url_param[:-1]).replace("compgroups", "servers/server_name/components") + "/" + comp_name
                                                                        url = self.get_url(url, server_name, self.enterprise_name)
                                                                        retry = True
                                                                        count = 0
                                                                        while retry:
                                                                            logger.info(f"Validating component {comp_name} ")
                                                                            response = requests.get(
                                                                                url=url,
                                                                                auth=(
                                                                                    self.auth_user,
                                                                                    self.auth_password
                                                                                ),
                                                                                headers=self.headers,
                                                                                verify=cert_path
                                                                            )
                                                                            logger.debug(f"{response}{response.text}")

                                                                            if "Error" in json.loads(response.text):

                                                                                logger.info("retrying")
                                                                            else:
                                                                                retry = False
                                                                            count = count + 1
                                                                            if count >= 5:
                                                                                retry = False
                                                                            sleep(2)

                                                                            logger.info(f"Response: {response}{response.text}\n")

                                                                            if response.status_code == 200:
                                                                                re = json.loads(response.text)
                                                                                if "Result" in re:
                                                                                    if re["Result"]:
                                                                                        if re["Result"][0]["CP_STARTMODE"] == "Auto":
                                                                                            retry = True
                                                                                            count = 0
                                                                                            while retry:

                                                                                                payload = {"Action": "manual start"}
                                                                                                logger.debug(f"{payload}")

                                                                                                response = requests.post(
                                                                                                    url=url,
                                                                                                    auth=(self.auth_user, self.auth_password),
                                                                                                    headers=self.headers,
                                                                                                    data=json.dumps(payload),
                                                                                                    verify=cert_path
                                                                                                )

                                                                                                if "Error" in json.loads(response.text):

                                                                                                    logger.info("retrying")
                                                                                                else:
                                                                                                    retry = False
                                                                                                count = count + 1

                                                                                                if count >= 5:
                                                                                                    retry = False
                                                                                                sleep(2)

                                                                                                logger.info(f"Response: {response}{response.text}\n")

                                                    for k, v in server_dict[parent_node]["component_groups"][parent_cg_key]["components"].items():
                                                        url = self.get_url(
                                                            v["url"],
                                                            server_name=server_name,
                                                            enterprise_name=self.enterprise_name
                                                        )
                                                        logger.debug(f"Enable component {k} of comp group {parent_cg_key}\n")

                                                        logger.info(f"Validating component {k} ")
                                                        response = requests.get(url=url,
                                                                                auth=(self.auth_user, self.auth_password),
                                                                                headers=self.headers,
                                                                                verify=cert_path)

                                                        logger.info(f"Response: {response}{response.text}\n")
                                                        if response.status_code == 200:
                                                            re = json.loads(response.text)
                                                            if "Result" in re:
                                                                if re["Result"]:
                                                                    if re["Result"][0]["CP_STARTMODE"] != "Auto":
                                                                        payload = {
                                                                            "Action": "auto start"
                                                                        }
                                                                        logger.debug(f"{payload}")

                                                                        response = requests.post(
                                                                            url=url,
                                                                            auth=(self.auth_user, self.auth_password),
                                                                            headers=self.headers,
                                                                            data=json.dumps(payload),
                                                                            verify=cert_path
                                                                        )

                                                                        logger.debug(f"Response : {response} {response.text}\n")

                                                        parameters = self.run_all_parameters(v["parameters"], server_name)
                                                        payload = {"Action": "auto start"}
                                                        if 'components' not in self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][parent_cg_key]:
                                                            self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][parent_cg_key]["components"] = {
                                                                k: {}
                                                            }

                                                        if k not in self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][parent_cg_key]["components"]:
                                                            self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][parent_cg_key]["components"][k] = {}

                                                        self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][parent_cg_key]["components"][k]["definition"] = payload
                                                        if parameters:
                                                            self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][parent_cg_key]["components"][k]["parameters"] = parameters

                                                        self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][parent_cg_key]["components"][k]["url"] = v["url"]

                                                        #     if 'components' not in self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][key]:
                                                        #         self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][key]["components"] = { k : {}}
                                                        #
                                                        #     if k not in self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][key]["components"]:
                                                        #         self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][key]["components"][k] = {}
                                                        #
                                                        #     self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][key]["components"][k]["definition"] = payload
                                                        #     self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][key]["components"][k]["parameters"] = parameters
                                                        #     self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][key]["components"][k]["url"]        = v["url"]

                                    # component comparison
                                    else:
                                        if "components" in value:
                                            for k, v in value["components"].items():
                                                # new component added
                                                if k not in cached_server_dict[parent_node]["component_groups"][parent_cg_key]["components"]:
                                                    logger.info(f"New component {k} addition identified")

                                                    url = self.get_url(v["url"], server_name, self.enterprise_name)
                                                    logger.info(f"Validating component {k} ")
                                                    response = requests.get(
                                                        url=url,
                                                        auth=(self.auth_user, self.auth_password),
                                                        headers=self.headers,
                                                        verify=cert_path
                                                    )

                                                    logger.info(f"Response: {response}{response.text}\n")
                                                    payload = None
                                                    if response.status_code == 200:
                                                        re = json.loads(response.text)
                                                        if "Result" in re:
                                                            if re["Result"]:
                                                                if re["Result"][0]["CP_STARTMODE"] != "Auto":

                                                                    url = self.get_url(v["url"], server_name, self.enterprise_name)

                                                                    payload = {"Action": "auto start"}
                                                                    logger.info(f"{payload}\n")

                                                                    response = requests.post(
                                                                        url=url,
                                                                        auth=(self.auth_user, self.auth_password),
                                                                        headers=self.headers,
                                                                        data=json.dumps(payload),
                                                                        verify=cert_path
                                                                    )

                                                                    logger.info(f"Response : {response}{response.text}\n")
                                                                else:
                                                                    logger.info("Component is already in auto start mode\n")

                                                        # put all component parameters
                                                        logger.info(f"Running all parameters for new component {k}\n")
                                                        parameters = self.run_all_parameters(v["parameters"], server_name)

                                                        if 'components' not in self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][parent_cg_key]:
                                                            self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][parent_cg_key]["components"] = {}
                                                            self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][parent_cg_key]["components"].update({k: {}})

                                                        if k not in self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][parent_cg_key]["components"]:
                                                            self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][parent_cg_key]["components"][k] = {}

                                                        self.restart_dict['enterprise']['siebserver'][server_name]['component_groups'][parent_cg_key]['components'][k].update({'definition': payload})
                                                        self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][parent_cg_key]["components"][k]["parameters"] = parameters
                                                        self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][parent_cg_key]["components"][k]["url"] = v["url"]
                                                else:
                                                    # component parameter comparison
                                                    if "parameters" in v:
                                                        comp_param_dict = v["parameters"]
                                                        cached_comp_param_dict = \
                                                        cached_server_dict[parent_node]["component_groups"][parent_cg_key]["components"][k]["parameters"]

                                                        logger.debug(f"\nComponent {k} parameter comparison")

                                                        flag, parameters = self.parameters_comparison(
                                                            comp_param_dict, cached_comp_param_dict,
                                                            server_name=server_name
                                                        )
                                                        if 'components' not in self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][parent_cg_key] and parameters:
                                                            self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][parent_cg_key]["components"] = {k: {}}

                                                        if flag:
                                                            if k not in self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][parent_cg_key]["components"]:
                                                                self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][parent_cg_key]["components"][k] = {}

                                                            self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][parent_cg_key]["components"][k]["parameters"] = parameters
                                                            self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][parent_cg_key]["components"][k]["url"] = v["url"]

                                # Deleting comp group
                                for p_cg_key_name, value in cached_server_dict[parent_node]["component_groups"].items():

                                    if p_cg_key_name not in server_dict[parent_node]["component_groups"]:
                                        logger.info(f"Disable comp group {p_cg_key_name}")

                                        for k, v in cached_server_dict[parent_node]["component_groups"][p_cg_key_name]["components"].items():
                                            url = self.get_url(
                                                v["url"],
                                                server_name=server_name,
                                                enterprise_name=self.enterprise_name
                                            )

                                            logger.debug(f"Disable component {k} of comp group {p_cg_key_name}\n")

                                            logger.info(f"Validating component {k} ")
                                            response = requests.get(
                                                url=url,
                                                auth=(self.auth_user, self.auth_password),
                                                headers=self.headers,
                                                verify=cert_path
                                            )

                                            logger.info(f"Response: {response}{response.text}\n")
                                            if response.status_code == 200:
                                                re = json.loads(response.text)
                                                if "Result" in re:
                                                    if re["Result"]:
                                                        if re["Result"][0]["CP_STARTMODE"] == "Auto":
                                                            payload = {"Action": "manual start"}
                                                            logger.debug(f"{payload}")

                                                            response = requests.post(
                                                                url=url,
                                                                auth=(self.auth_user, self.auth_password),
                                                                headers=self.headers,
                                                                data=json.dumps(payload),
                                                                verify=cert_path
                                                            )

                                                            logger.debug(f"Response : {response} {response.text}\n")

                                        # Disable component group
                                        url = value["url"].replace("compgroups", "servers/server_name/compgroups")
                                        url = self.get_url(url, server_name, self.enterprise_name)
                                        payload = {
                                            "Action": "disable"
                                        }

                                        logger.info(f"disable comp group: {p_cg_key_name} : {url} : {payload}")

                                        response = requests.post(
                                            url=url,
                                            auth=(self.auth_user, self.auth_password),
                                            headers=self.headers,
                                            data=json.dumps(payload),
                                            verify=cert_path
                                        )

                                        logger.info(f" Response : {response}{response.text}\n")

                                        if server_name not in self.restart_dict["enterprise"]["siebserver"]:
                                            self.restart_dict["enterprise"]["siebserver"][server_name] = {}
                                        if p_cg_key_name not in self.restart_dict["enterprise"]["siebserver"][server_name]:
                                            self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][p_cg_key_name] = {}
                                        self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][p_cg_key_name]["definition"] = {}
                                        self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][p_cg_key_name]["url"] = value["url"]

                                    # component comparison
                                    else:
                                        if "components" in value:
                                            for k, v in value["components"].items():
                                                # delete component

                                                if k not in server_dict[parent_node]["component_groups"][p_cg_key_name]["components"]:
                                                    logger.info(f"Disable  component {k}\n")
                                                    url = self.get_url(v["url"], server_name, self.enterprise_name)
                                                    logger.info(f"Validating component {k} ")
                                                    response = requests.get(
                                                        url=url,
                                                        auth=(self.auth_user, self.auth_password),
                                                        headers=self.headers,
                                                        verify=cert_path
                                                    )

                                                    logger.info(f"Response: {response}{response.text}\n")

                                                    if response.status_code == 200:
                                                        re = json.loads(response.text)
                                                        if "Result" in re:
                                                            if re["Result"]:
                                                                if re["Result"][0]["CP_STARTMODE"] == "Auto":
                                                                    payload = {"Action": "manual start"}
                                                                    logger.info(f"Step 1 : manual start component {k} {payload}")

                                                                    response = requests.post(url=url,
                                                                                             auth=(self.auth_user, self.auth_password),
                                                                                             headers=self.headers,
                                                                                             data=json.dumps(payload),
                                                                                             verify=cert_path)
                                                                    logger.info(f" Response : {response}{response.text}\n")
                                                                    # # pause
                                                                    # payload =  {"Action": "Pause"}
                                                                    #
                                                                    # logger.info(f"Step 2 : Pause component {k} {payload}")
                                                                    # response = requests.post(url=url,
                                                                    #                          auth=( self.auth_user,self.auth_password),
                                                                    #                          headers=self.headers,
                                                                    #                          data=json.dumps(payload),
                                                                    #                          verify=cert_path)
                                                                    # logger.info(f" Response : {response}{response.text}\n")
                                                                    #
                                                                    # # shutdown
                                                                    # payload =  {"Action": "Shutdown"}
                                                                    # logger.info(f"Step 3 : Shutdown component {k} {payload}")
                                                                    # response = requests.post(url     = url,
                                                                    #                          auth    = ( self.auth_user,self.auth_password),
                                                                    #                          headers = self.headers,
                                                                    #                          data    = json.dumps(payload),
                                                                    #                          verify  = False)
                                                                    # logger.info(f" Response : {response}{response.text}\n")

                                                                    if 'components' not in self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][p_cg_key_name]:
                                                                        self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][p_cg_key_name] = {'components': {}}
                                                                    if k not in self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][p_cg_key_name]['components']:
                                                                        self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][p_cg_key_name]['components'][k] = {}
                                                                    self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][p_cg_key_name]["components"][k]["definition"] = {}
                                                                    self.restart_dict["enterprise"]["siebserver"][server_name]["component_groups"][p_cg_key_name]["components"][k]["url"] = v["url"]
                                                                else:
                                                                    logger.info("Component is already in manual start mode\n")

                copyfile(yaml_file, cached_yaml)

    def crm_restart_algorithm(self):
        """
        CRM Restart method
        @return: None
        """
        global namespace
        logger.debug("crm_restart_algorithm\n")

        enterprise_flag = False
        data = self.restart_dict

        logger.debug(f"\n\nRestart_dict: {self.restart_dict}\n\n")

        if "parameters" in data["enterprise"]:
            logger.debug("enterprise restart logic\n")
            for item in data["enterprise"]["parameters"]:
                for (item_key, value) in item.items():
                    if item_key != "url":
                        for k, v in value.items():
                            url = self.get_url(item["url"], enterprise_name=self.enterprise_name)
                            url = self.get_parameter_url(url, k)

                            response = requests.get(
                                url=url,
                                auth=(self.auth_user, self.auth_password),
                                headers=self.headers,
                                verify=cert_path
                            )

                            re = json.loads(response.text)
                            if response.status_code == 200:
                                if "Result" in re:
                                    if re["Result"]:
                                        PA_EFF_SRVR_RSTRT = re["Result"][0]["PA_EFF_SRVR_RSTRT"] # NOQA
                                        PA_EFF_CMP_RSTRT  = re["Result"][0]["PA_EFF_CMP_RSTRT"] # NOQA
                                        logger.debug(f"PA_EFF_CMP_RSTRT : {PA_EFF_CMP_RSTRT} ,PA_EFF_SRVR_RSTRT : {PA_EFF_SRVR_RSTRT} ")
                                        if PA_EFF_CMP_RSTRT == "Y" or PA_EFF_SRVR_RSTRT == "Y":
                                            enterprise_flag = True

            logger.debug(f"\n\nEnterprise : Enterprise_flag : {enterprise_flag}\n\n")

        if "named_subsystem" in data["enterprise"]:
            logger.debug("named_subsystem restart logic\n")

            for ns_key, value in data["enterprise"]["named_subsystem"].items():
                if "definition" in data["enterprise"]["named_subsystem"][ns_key]:
                    if data["enterprise"]['named_subsystem'][ns_key]['definition']:
                        logger.info("New named subsystem added : No restart required\n")
                    else:
                        logger.info("A named subsystem is deleted : No restart required\n")
                if "parameters" in data["enterprise"]["named_subsystem"][ns_key]:
                    logger.debug("Change parameter are")
                    logger.debug(data["enterprise"]["named_subsystem"][ns_key]['parameters'])
                    for item in data["enterprise"]["named_subsystem"][ns_key]['parameters']:
                        for (k, v) in item.items():
                            if k != "url":
                                for k1, v1 in v.items():
                                    url = self.get_url(item["url"], enterprise_name=self.enterprise_name)
                                    url = self.get_parameter_url(url, k1)

                                    url = self.get_url(url, enterprise_name=self.enterprise_name)

                                    response = requests.get(url=url,
                                                            auth=(self.auth_user,
                                                                  self.auth_password),
                                                            headers=self.headers,
                                                            verify=cert_path)

                                    re = json.loads(response.text)
                                    if "Result" in re:
                                        if re["Result"]:
                                            PA_EFF_SRVR_RSTRT = re["Result"][0]["PA_EFF_SRVR_RSTRT"] # NOQA
                                            PA_EFF_CMP_RSTRT = re["Result"][0]["PA_EFF_CMP_RSTRT"] # NOQA

                                            logger.info(f"PA_EFF_CMP_RSTRT : {PA_EFF_CMP_RSTRT} ,PA_EFF_SRVR_RSTRT : {PA_EFF_SRVR_RSTRT} ")

                                            if PA_EFF_SRVR_RSTRT == "Y" or PA_EFF_CMP_RSTRT == "Y":
                                                enterprise_flag = True

            logger.debug(f"\n\nNamed_subsystem : Enterprise_flag  : {enterprise_flag}\n\n")

        if "component_definitions" in data["enterprise"]:
            logger.debug("component_definitions restart logic\n")
            for _, value in data["enterprise"]["component_definitions"].items():
                if "definition" in value:
                    # no restart or server restart - need to verify
                    if value["definition"]:
                        logger.info("New component definitions added : No restart required\n")
                    else:
                        logger.info("A component definitions deleted : No restart required\n")

                if "parameters" in value:
                    for item in value["parameters"]:
                        for (k, v) in item.items():
                            if k != "url":
                                logger.debug(f"Changed parameters is {k} : {v}")
                                for k1, v1 in v.items():
                                    url = self.get_url(item["url"], enterprise_name=self.enterprise_name)
                                    url = self.get_parameter_url(url, k1)

                                    response = requests.get(url=url,
                                                            auth=(self.auth_user, self.auth_password),
                                                            headers=self.headers,
                                                            verify=cert_path)

                                    if response.status_code == 200:
                                        re = json.loads(response.text)

                                        if "Result" in re:
                                            if re["Result"]:
                                                PA_EFF_SRVR_RSTRT = re["Result"][0]["PA_EFF_SRVR_RSTRT"] # NOQA
                                                PA_EFF_CMP_RSTRT = re["Result"][0]["PA_EFF_CMP_RSTRT"] # NOQA
                                                logger.info(
                                                    f"PA_EFF_CMP_RSTRT : {PA_EFF_CMP_RSTRT} ,PA_EFF_SRVR_RSTRT : {PA_EFF_SRVR_RSTRT} ")

                                                if PA_EFF_SRVR_RSTRT == "Y" or PA_EFF_CMP_RSTRT == "Y":
                                                    enterprise_flag = True

            logger.debug(f"\n\nComponent_Definitions : Enterprise_flag : {enterprise_flag}\n\n")

        if "component_groups" in data["enterprise"]:
            logger.debug("component_groups restart logic\n")
            for _, value in data["enterprise"]["component_groups"].items():
                if "definition" in value:
                    if value["definition"]:
                        logger.info(f"New comp group added : No restart required\n")
                    else:
                        logger.info(f"A comp group is deleted : No restart required\n")

        if enterprise_flag:
            logger.info(f"Enterprise Flag is True : Restart all sieb servers\n\n")
            for server_key_name, value in data["enterprise"]['siebserver'].items():
                logger.info(f"\n\nServer_name : {server_key_name}")
                self.restart_server(server_key_name, namespace)
        else:

            if "siebserver" in data["enterprise"]:

                for server_key_name, value in data["enterprise"]["siebserver"].items():
                    server_restart = False

                    server_name = server_key_name
                    if "parameters" in value:
                        for item in value["parameters"]:
                            for (k, v) in item.items():
                                if k != "url":
                                    for k1, v1 in v.items():
                                        url = self.get_parameter_url(item["url"], k1)
                                        url = self.get_url(url, server_name, self.enterprise_name)

                                        response = requests.get(url=url,
                                                                auth=(self.auth_user, self.auth_password),
                                                                headers=self.headers,
                                                                verify=cert_path)

                                        if response.status_code == 200:
                                            re = json.loads(response.text)

                                            if "Result" in re:
                                                if re["Result"]:
                                                    PA_EFF_SRVR_RSTRT = re["Result"][0]["PA_EFF_SRVR_RSTRT"] # NOQA
                                                    PA_EFF_CMP_RSTRT = re["Result"][0]["PA_EFF_CMP_RSTRT"] # NOQA

                                                    logger.debug(f"\n\nPA_EFF_CMP_RSTRT : {PA_EFF_CMP_RSTRT} ,PA_EFF_SRVR_RSTRT : {PA_EFF_SRVR_RSTRT} \n {re}\n ")

                                                    if re["Result"][0]["PA_EFF_SRVR_RSTRT"] == "Y" or re["Result"][0]["PA_EFF_CMP_RSTRT"] == "Y":
                                                        server_restart = True

                    if "component_groups" in value:
                        for k1, v1 in value["component_groups"].items():
                            if "definition" in v1:
                                server_restart = True
                                break

                            if "components" in v1 and not server_restart:
                                for k2, v2 in v1["components"].items():
                                    component_restart = False
                                    if "definition" in v2:
                                        server_restart = True
                                    if "parameters" in v2:
                                        for item in v2["parameters"]:
                                            for (k3, v3) in item.items():
                                                if k3 != "url":
                                                    for k4, v4 in v3.items():
                                                        url = self.get_url(item["url"], server_name, self.enterprise_name)

                                                        url = self.get_parameter_url(url, k4)

                                                        response = requests.get(url=url,
                                                                                auth=(self.auth_user, self.auth_password),
                                                                                headers=self.headers,
                                                                                verify=cert_path)

                                                        if response.status_code == 200:
                                                            re = json.loads(response.text)
                                                            if "Result" in re:
                                                                if re["Result"]:
                                                                    PA_EFF_CMP_RSTRT = re["Result"][0]["PA_EFF_CMP_RSTRT"] # NOQA
                                                                    PA_EFF_SRVR_RSTRT = re["Result"][0]["PA_EFF_SRVR_RSTRT"] # NOQA
                                                                    logger.debug(
                                                                        f"\n\nPA_EFF_CMP_RSTRT : {PA_EFF_CMP_RSTRT} ,PA_EFF_SRVR_RSTRT : {PA_EFF_SRVR_RSTRT} \n {re}\n ")
                                                                    if re["Result"][0]["PA_EFF_SRVR_RSTRT"] == "Y":
                                                                        server_restart = True
                                                                        logger.debug(f"\n\nServer_restart : {server_restart}\n\n")
                                                                        break
                                                                    if re["Result"][0]["PA_EFF_CMP_RSTRT"] == "Y":
                                                                        component_restart = True
                                                                        logger.debug(f"\n\ncomponent_restart : {component_restart}\n\n")
                                                                        pass

                                    if server_restart:
                                        break
                                    elif component_restart:
                                        logger.info(f"\nRestarting component {k2}\n")
                                        # url = https://slc17tzg.us.oracle.com:16691/siebel/v1.0/cloudgateway/enterprises/siebel/servers/slc17tzg/components/CGMObjMgr_enu
                                        retry_flag = True
                                        count = 0
                                        url = self.get_url(v2["url"], server_name, self.enterprise_name)

                                        payload = {"Action": "Shutdown"}

                                        logger.info(f"\nPayload : {payload}\n, Url : {url}\n")

                                        while retry_flag:
                                            response = requests.post(url=url,
                                                                     auth=(self.auth_user, self.auth_password),
                                                                     headers=self.headers,
                                                                     data=json.dumps(payload),
                                                                     verify=cert_path)
                                            logger.info(f"\n{response} \n {response.text}\n")

                                            if "Error" in json.loads(response.text):
                                                logger.info("\nRetrying api\n")
                                                pass
                                            else:
                                                retry_flag = False
                                            count = count + 1
                                            sleep(2)
                                            if count == 5:
                                                break

                                        payload = {"Action": "Startup"}

                                        logger.info(f"\nPayload : {payload}\n, Url : {url}\n")
                                        retry_flag = True
                                        count = 0
                                        while retry_flag:
                                            response = requests.post(url=url,
                                                                     auth=(self.auth_user, self.auth_password),
                                                                     headers=self.headers,
                                                                     data=json.dumps(payload),
                                                                     verify=cert_path)
                                            logger.info(f"\n{response} \n {response.text}\n")

                                            if "Error" in json.loads(response.text):
                                                logger.info("\nRetrying api\n")
                                                pass
                                            else:
                                                retry_flag = False
                                            count = count + 1
                                            sleep(2)
                                            if count == 5:
                                                break

                    if server_restart:
                        self.restart_server(server_name, namespace)

    def scs_restart_algorithm(self):
        """
        SCS Restart method
        @return: None
        """
        logger.debug("scs_restart_algorithm\n")

        logger.debug(f"\n\nRestart_dict: {self.restart_dict}\n\n")
        data = self.restart_dict
        self.scs_full_restart = False
        self.comp_restart_list = set()

        if "enterprise" in data:
            if "sai_profile" in data["enterprise"]:
                if data["enterprise"]["sai_profile"]:
                    self.scs_full_restart = True

            if "parameters" in data["enterprise"]:
                logger.debug("enterprise runtime restart logic\n")
                for item in data["enterprise"]["parameters"]:
                    for (item_key, value) in item.items():
                        if item_key != "url":
                            if value:
                                self.scs_full_restart = True
                                break

            if "named_subsystem" in data["enterprise"] and not self.scs_full_restart:
                logger.debug("named subsystem restart logic\n")
                for e_ns_key, value in data["enterprise"]["named_subsystem"].items():
                    if "definition" in data["enterprise"]["named_subsystem"][e_ns_key]:
                        if data["enterprise"]['named_subsystem'][e_ns_key]['definition']:
                            logger.debug("new named subsystem added")
                            logger.debug("No restart required")
                    if "parameters" in data["enterprise"]["named_subsystem"][e_ns_key]:
                        logger.debug("Change parameter are")
                        logger.debug(data["enterprise"]["named_subsystem"][e_ns_key]['parameters'])
                        for item in data["enterprise"]["named_subsystem"][e_ns_key]['parameters']:
                            for (k, v) in item.items():
                                if k != "url":
                                    if v:
                                        self.scs_full_restart = True
                                        break

            if "component_definitions" in data["enterprise"] and not self.scs_full_restart:
                logger.debug("component_definitions restart logic\n")
                for _, value in data["enterprise"]["component_definitions"].items():
                    if "definition" in value:
                        # no restart or server restart - need to verify
                        pass
                    if "parameters" in value:
                        for item in value["parameters"]:
                            for (k, v) in item.items():
                                if k != "url":
                                    logger.debug(f"Changed parameters are {k} : {v}")
                                    if v:
                                        self.scs_full_restart = True
                                        break

            if "component_groups" in data["enterprise"] and not self.scs_full_restart:
                for e_cg_key, value in data["enterprise"]["component_groups"].items():
                    if "definition" in value:
                        if value["definition"]:
                            logger.debug(f"New comp group is {e_cg_key}")
                        else:
                            logger.debug(f"deleted comp group is {e_cg_key}")

            if "siebserver" in data["enterprise"] and not self.scs_full_restart:
                logger.debug("siebserver restart logic\n")
                for _, value in data["enterprise"]["siebserver"].items():
                    if "parameters" in value:
                        for item in value["parameters"]:
                            for (k, v) in item.items():
                                if k != "url":
                                    if v:
                                        self.scs_full_restart = True
                                        break

                    if "component_groups" in value:
                        for k1, v1 in value["component_groups"].items():
                            if "definition" in v1:
                                self.scs_full_restart = True
                                break

                            if "components" in v1 and not self.scs_full_restart:
                                for k2, v2 in v1["components"].items():
                                    if "definition" in v2:
                                        self.scs_full_restart = True
                                        break
                                    if "parameters" in v2:
                                        for item in v2["parameters"]:
                                            for (k3, v3) in item.items():
                                                if k3 != "url":
                                                    if v3:
                                                        self.comp_restart_list.add(k2.replace("_", "-").lower())
                                                        pass

        logger.debug(f"scs_full_restart flag :{self.scs_full_restart}\n")

        if self.scs_full_restart:

            command = "kubectl -n {} get deploy -o=name".format(namespace)
            response = subprocess.Popen(
                command,
                shell=True,
                encoding='utf8',
                stdin=None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            deployments = response.stdout.readlines()
            logger.info("Restarting all SCS deployments\n")
            for i in deployments:
                deploy_name = i.replace("deployment.apps/", "").strip()

                if deploy_name == "siebcfg" or deploy_name == "siebdb" or deploy_name == "siebel-controller" or deploy_name == "ingress-nginx-controller":
                    pass
                else:
                    logger.info(f"Restarting deployment {deploy_name}\n")
                    command = "kubectl -n {} rollout restart deploy/{}".format(namespace, deploy_name)
                    response = subprocess.check_output(command, shell=True, encoding='utf8').strip()
                    logger.debug(response)

        else:
            for comp in self.comp_restart_list:
                logger.info(f"Restarting component {comp}")
                command = "kubectl -n {} rollout restart deploy/{}".format(namespace, comp)
                response = subprocess.check_output(command, shell=True, encoding='utf8').strip()
                logger.debug(response)


class Controller(BaseHTTPRequestHandler):

    k8s_cert_path = '/var/run/secrets/kubernetes.io/serviceaccount/ca.crt'
    client_cert_path = '/certs/ca.cert.pem'

    def create_cm(self, name, name_space, payload):
        """
        Create a config Map
        @param name: name of the config map
        @param name_space: namespace in which to be created
        @param payload: content to be filled in the config map
        @return: None
        """
        self.headers = {'accept': 'application/json', 'Content-Type': 'application/json'}
        api_server = "https://kubernetes.default.svc"
        token = subprocess.Popen(
            'cat /var/run/secrets/kubernetes.io/serviceaccount/token',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True
        )
        token = token.communicate()[0].decode("utf-8")
        url = api_server + "/api/v1/namespaces/{}/configmaps/{}".format(name_space, name)

        logger.debug(f"Cached cm name : {name}\n")
        retry = True
        count = 0
        while retry:
            response = requests.put(
                url,
                auth=BearerAuth(token),
                json=payload,
                verify=self.k8s_cert_path,
                headers=self.headers
            )
            logger.debug(f"response status: {response.status_code}\n")
            if response.status_code == 200:
                logger.debug(f"Updated cm {name}\n")
                retry = False
            elif response.status_code != 200:
                count = count + 1
                url = api_server + "/api/v1/namespaces/{}/configmaps".format(name_space)
                logger.debug(f"Creating cm {name}")
                response = requests.post(
                    url,
                    auth=BearerAuth(token),
                    json=payload,
                    verify=self.k8s_cert_path,
                    headers=self.headers
                )
                logger.debug(f"response status: {response.status_code}\n")
                if count >= 4 or response.status_code == 201 or response.status_code == 200:
                    retry = False

    def sync(self, parent: dict, related: dict) -> list:
        """
        Method to sync config maps
        @param parent: parent config map
        @param related: related info
        @return: None
        """
        sourceNamespace: str = parent['spec']['sourceNamespace'] # NOQA
        sourceName: str = parent['spec']['sourceName'] # NOQA

        if len(related['ConfigMap.v1']) == 0:
            logger.debug("Related resource has been deleted, clean-up copies")
            return []

        files = [f for f in os.listdir(self.cache_yaml_base_path) if os.path.isfile(os.path.join(self.cache_yaml_base_path, f))]
        target_configmaps = []
        logger.debug("\n\nCreating/Updating cached cms from files\n\n")

        for fname in files:
            logger.debug(os.path.join(self.cache_yaml_base_path, fname))
            name = fname.split(".")[0].replace("_", "-")

            if "aiprofile" in fname:
                name = "cached-aiprofile-config"

            cache_data = {}
            data = IncrementalChanges().parse_yaml_string(os.path.join(self.cache_yaml_base_path, fname))
            cache_data[fname] = yaml.dump(data)
            cm = self.new_configmap(name, sourceNamespace, cache_data)
            target_configmaps.append(cm)
            self.create_cm(name_space=sourceNamespace, name=name, payload=cm)

        return target_configmaps

    @staticmethod
    def new_configmap(name: str, name_space: str, data: dict) -> dict:
        """
        Sample placeholder for a config map
        @param name: Name of the configmap
        @param name_space: namespace in which to be created
        @param data: content of the config map
        @return: dict - sample config map
        """
        return {
            'apiVersion': 'v1',
            'kind': 'ConfigMap',
            'metadata': {
                'name': name,
                'namespace': name_space
            },
            'data': data
        }

    @staticmethod
    def customize(source_name: str, source_namespace: str) -> list:
        """
        Sample placeholder for customizing config map
        @param source_name: name
        @param source_namespace: namespace name
        @return: dict
        """
        return [
            {
                'apiVersion': 'v1',
                'resource': 'configmaps',
                'namespace': source_namespace,
                'names': [source_name]
            }
        ]

    def get_all_config_maps(self, name_space, data):
        """
        Fetch all config maps
        @param name_space: namespace from where to fetch
        @param data: content
        @return: None
        """
        api_server = "https://kubernetes.default.svc"
        token = subprocess.Popen(
            'cat /var/run/secrets/kubernetes.io/serviceaccount/token',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True
        )
        token = token.communicate()[0].decode("utf-8")
        logger.debug("\n\nget_all_config_maps\n")
        for item_key, value in data.items():
            if item_key == "aiprofile.json":
                item_key = "aiprofile-config"

            logger.debug(f"key : {item_key}")
            url = api_server + "/api/v1/namespaces/{}/configmaps/{}".format(name_space, item_key)
            response = requests.get(
                url,
                auth=BearerAuth(token),
                verify=self.k8s_cert_path
            )
            logger.debug(f"\nresponse : {response}\n")
            logger.debug(f"\nresponse text: {response.text}\n")
            logger.debug('request url - {}'.format(url))
            if response.status_code == 200:
                parsed_yaml = yaml.safe_load(response.text)
                try:
                    parsed_yaml = yaml.safe_load(parsed_yaml)
                except Exception as e:
                    logger.error('error while parsing yaml file')
                    logger.error(str(e))
                    pass

                config_data = parsed_yaml["data"]
                k, v = list(config_data.items())[0]
                path = self.yaml_base_path + "/" + k

                with open(path, 'w') as outfile:
                    yaml.dump(yaml.safe_load(v), outfile, default_flow_style=False)

            logger.debug(f"\nGetting cached data from configmaps\n")
            cached_name = "cached-" + item_key
            url = api_server + "/api/v1/namespaces/{}/configmaps/{}".format(name_space, cached_name)
            response = requests.get(
                url,
                auth=BearerAuth(token),
                verify=self.k8s_cert_path
            )
            logger.debug(f"response : {response}")
            if response.status_code == 200:
                config_data = yaml.safe_load(response.text)["data"]
                k, v = list(config_data.items())[0]
                path = self.cache_yaml_base_path + "/" + k
                with open(path, 'w') as outfile:
                    yaml.dump(yaml.safe_load(v), outfile, default_flow_style=False)


    def do_POST(self):
        """
        Default callable for the HTTP server
        @return: http:Server
        """
        self.running = False
        self.yaml_base_path = "/home/siebel/config"
        self.cache_yaml_base_path = "/home/siebel/config/cached"
        if self.path == '/sync':
            if self.running:
                sleep(30)
            self.running = True

            os.makedirs(self.cache_yaml_base_path, exist_ok=True)
            os.makedirs(self.yaml_base_path, exist_ok=True)
            observed: dict = json.loads(self.rfile.read(
                int(self.headers.get('content-length'))))
            parent: dict = observed['parent']
            logger.debug("/sync %s", parent['metadata']['name'])
            related: dict = observed['related']

            source_name = parent['spec']['sourceName']
            source_namespace = parent['spec']['sourceNamespace']
            ns = open("/var/run/secrets/kubernetes.io/serviceaccount/namespace", "r").read()
            logger.debug("Current ns: {}".format(ns))
            if source_namespace == ns:
                data = related['ConfigMap.v1'][f'{source_namespace}/{source_name}']['data']

                self.get_all_config_maps(source_namespace, data)

                global namespace
                namespace = source_namespace
                logger.info(f"\n Incremental Algorithm\n")
                incremental = IncrementalChanges()

                incremental.enterprise_runtime()
                incremental.named_subsystem_runtime()
                incremental.comp_defs_runtime()
                incremental.server_runtime()

                deployment_type = parent['spec']['deployment_type']

                if deployment_type.lower() == "crm":
                    incremental.sai_crm_runtime()
                    incremental.crm_restart_algorithm()
                elif deployment_type.lower() == "scs":
                    self.scs_full_restart = False
                    incremental.sai_scs_runtime()
                    incremental.scs_restart_algorithm()

                expected_copies: int = 1
                actual_copies: int = len(observed['children']['ConfigMap.v1'])
                response: dict = {
                    'status': {
                        'expected_copies': expected_copies,
                        'actual_copies': actual_copies
                    },
                    'children': self.sync(parent, related)
                }

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode('utf-8'))
            else:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()

        elif self.path == '/customize':
            request: dict = json.loads(self.rfile.read(
                int(self.headers.get('content-length'))))
            parent: dict = request['parent']
            logger.debug("/customize %s", parent['metadata']['name'])
            ns = open("/var/run/secrets/kubernetes.io/serviceaccount/namespace", "r").read()
            logger.debug("Current ns: {}".format(ns))
            if parent['spec']['sourceNamespace'] == ns:
                related_resources: dict = {
                    'relatedResources': self.customize(
                        parent['spec']['sourceName'],
                        parent['spec']['sourceNamespace']
                    )
                }
                logger.debug("Related resources: \n %s", related_resources)
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(related_resources).encode('utf-8'))
            else:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()

        else:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            error_msg: dict = {
                'error': '404',
                'endpoint': self.path
            }

            self.wfile.write(json.dumps(error_msg).encode('utf-8'))


port = os.getenv("Port", "1025")
ssl_context = SSLContext(PROTOCOL_TLS_SERVER)
ssl_context.load_cert_chain("/certs/tls.crt", "/certs/tls.key", "siebel")
server = HTTPServer(("0.0.0.0", int(port)), Controller)
server.socket = ssl_context.wrap_socket(server.socket, server_side=True)
server.serve_forever()