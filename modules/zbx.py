#!/usr/bin/env python3
# %%
import os, sys
import asyncio
from pyzabbix import ZabbixAPI, ZabbixAPIException
import urllib3
from time import sleep
from datetime import datetime
from modules.gets import get_user_passwd, get_url, get_date_month
from modules.banner import banner


def zbx_connect(zbxname: str = "Zabbix", url: str = "", api_token: str = ""):

    zbxname = zbxname.upper().strip()
    if not url:
        url = get_url(zbxname)
    url = url.strip()
    api_token = api_token.strip()

    banner(f"Connect Zabbix {zbxname}", bottom_text="")

    while True:
        zapi = ZabbixAPI(url)
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        zapi.session.verify = False

        try:
            if api_token:
                zapi.login(api_token=api_token)
            else:
                username, passwd = get_user_passwd(zbxname)
                zapi.login(username, passwd)

            print(f"Connected to Zabbix {zbxname} API Version {zapi.api_version()}.")
            sleep(1)
            break
        except ZabbixAPIException as error:
            os.system("cls" if os.name == "nt" else "clear")
            if "name or password" in str(error):
                print("[ERROR] Login name or password is incorrect")
            elif "Not Found for url" in str(error):
                print("[ERROR] Not Found for url")
                url = get_url()
            elif "Invalid URL" in str(error):
                print("[ERROR] " + str(error))
                url = get_url(zbxname)
            elif "Failed to establish a new connection" in str(error):
                print(f"[ERROR] Failed to establish a new connection `{url}`.")
                url = get_url(zbxname)
            else:
                print("aqui")
                print(type(error).__name__, error)
                sys.exit(1)
        except Exception as error:
            if type(error).__name__ == "MissingSchema":
                print(error)
                url = get_url(zbxname)
            elif type(error).__name__ == "ConnectionError":
                print("Connection error: Enter the correct URL")
                url = get_url(zbxname)
            else:
                print(f"[ERRO] {type(error).__name__}: {error}")
                sys.exit(1)

    return zapi


def get_problems(
    zapi: ZabbixAPI,
    hostid: str,
    month: int | None = 0,
    year: int | None = 0,
    alert_name: str = "Unavailable by ICMP ping",
) -> list:
    zapi = zapi
    hostid = hostid
    month = int(month) or datetime.now().month
    year = int(year) or datetime.now().year
    alert_name = alert_name

    time_from, time_till, *_ = get_date_month(month, year)

    resolveds = dict()
    for resolved in zapi.event.get(
        hostids=hostid,
        output=["name", "clock"],
        time_from=time_from,
        time_till=time_till,
        search={"name": alert_name},
        filter={"value": 0},
        sortfild="clock",
    ):
        resolveds[resolved["eventid"]] = resolved["clock"]

    problems = []
    for problem in zapi.event.get(
        hostids=hostid,
        output=["name", "clock", "r_eventid", "acknowledged", "value"],
        select_acknowledges=["message"],
        problem_time_from=time_from,
        problem_time_till=time_till,
        search={"name": alert_name},
        sortfild="clock",
    ):
        if problem["r_eventid"] != "0":
            r_clock = resolveds.get(problem["r_eventid"])
        else:
            r_clock = time_till - 1

        if not r_clock:
            r_clock = time_till - 1

        clock = problem["clock"] if int(problem["clock"]) >= time_from else time_from

        messages = []
        for e in problem["acknowledges"]:
            msg = ""
            if e.get("message"):
                msg = e["message"].strip().replace("\n", "/")
                msg = msg.replace("\r", "/")
                # msg = msg.replace(",", " | ")
            messages.append(msg)

        messages_join = "||".join(messages)
        clock = int(clock)
        r_clock = int(r_clock)
        delta = r_clock - clock
        info = {
            "hostid": hostid,
            "name": problem["name"],
            "hostid": hostid,
            "clock": clock,
            "r_clock": r_clock,
            "duration": delta,
            "ack": problem["acknowledged"],
            "messages": messages_join,
        }

        problems.append(info)
    return problems


def get_events(
    zapi: ZabbixAPI,
    hostid: str,
    month: int | None = 0,
    year: int | None = 0,
    alert_name: str = "",
) -> list[dict]:
    zapi = zapi
    hostid = hostid
    month = int(month) or datetime.now().month
    year = int(year) or datetime.now().year
    alert_name = alert_name

    time_from, time_till, *_ = get_date_month(month, year)

    events = []
    count_attempts_to_get_events = 0
    while True:
        try:
            event_results = zapi.event.get(
                hostids=hostid,
                output=[
                    "name",
                    "clock",
                    "r_eventid",
                    "acknowledged",
                    "value",
                    "objectid",
                ],
                select_acknowledges=["message"],
                time_from=time_from,
                time_till=time_till,
                search={"name": alert_name},
                sortfild=["clock"],
                sortorder="DESC",
                value="1",
                object="0",
            )
            break

        except Exception as error:
            print(error)
            count_attempts_to_get_events += 1
            if count_attempts_to_get_events >= 10:
                print("Falha ao tentar coletar info: hostid", hostid)
                event_results = []
                break
            sleep(2)

    if len(event_results) > 0:
        for event in event_results:
            messages = []
            for e in event["acknowledges"]:
                msg = ""
                if e.get("message"):
                    msg = e["message"].strip().replace("\n", "/")
                    msg = msg.replace("\r", "/")
                    # msg = msg.replace(",", " | ")
                messages.append(msg)

            messages_join = "||".join(messages)
            clock = int(event["clock"])
            info = {
                "hostid": hostid,
                "name": event["name"],
                "hostid": hostid,
                "clock": clock,
                "r_eventid": event["r_eventid"],
                "ack": event["acknowledged"],
                "messages": messages_join,
                "objectid": event["objectid"],
            }

            events.append(info)
    return events


def get_event_resolved(zapi, event):
    r_clock = 0
    if event.get("r_eventid") != "0" and event.get("r_eventid") is not None:
        count_attempts_to_get = 0
        while True:
            try:
                get_resolved_result = zapi.event.get(
                    eventids=event["r_eventid"],
                    output=["clock"],
                )
                if len(get_resolved_result) > 0:
                    r_clock = get_resolved_result[0]["clock"]
                break

            except Exception as error:
                print(error)
                count_attempts_to_get += 1

                if count_attempts_to_get >= 60:
                    print("Falha ao tentar coletar info: enventid", event["r_eventid"])
                    break
                asyncio.sleep(2)

    delta = int(r_clock) - int(event["clock"]) if r_clock != 0 else 0
    event["r_clock"] = r_clock
    event["duration"] = delta


def parms_get_hosts(
    zbx_version: float = 6.0,
    search: dict | None = {},
    filter: dict | None = {},
    **kwargs,
) -> dict:
    zbx_version = zbx_version
    parms = {
        "output": ["host", "name", "status"],
        "selectParentTemplates": ["name"],
        "selectTags": ["tag", "value"],
        "selectMacros": ["macro", "value"],
        "search": search,
        "filter": filter,
        "searchByAny": True,
        **kwargs,
    }

    if zbx_version > 6:
        parms["selectHostGroups"] = ["name", "groupid"]  # Zabbix >=6.0
    else:
        parms["selectGroups"] = ["name", "groupid"]  # Zabbix <=6.0

    return parms


def host_info(**host_get_return: dict) -> dict:
    host = {
        "hostid": host_get_return["hostid"],
        "host": host_get_return["host"],
        "name": host_get_return["name"],
        "status": "enabled" if host_get_return["status"] == "0" else "disabled",
        "tags": "",
        "macros": "",
    }

    templates = [i["name"] for i in host_get_return["parentTemplates"]]
    host["templates"] = ";".join(templates)

    if host_get_return.get("hostgroups"):
        groups = [i["name"] for i in host_get_return["hostgroups"]]
    else:
        groups = [i["name"] for i in host_get_return["groups"]]  # Zabbix <=6.0
    host["hostgroups"] = ";".join(groups)

    macros = []
    for macro in host_get_return["macros"]:
        macros.append(f"{macro['macro']}={macro['value']}")
    host["macros"] = ";".join(macros)

    tags = []
    for tag in host_get_return["tags"]:
        tags.append(f"{tag['tag']}={tag['value']}")
    host["tags"] = ";".join(tags)

    return host


################
class MyZabbix(ZabbixAPI):
    def __init__(self, zbxname: str = "Unknown", server: str = "", *args, **kwargs):
        self.zbxname = zbxname
        super().__init__(server=server, *args, **kwargs)
        # Disable SSL
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.session.verify = False
        self.__zbx_version = 6.0

    def connect(self, api_token: str = ""):

        if not self.server:
            self.server = get_url(self.zbxname)
        # self.server = self.server.strip()
        api_token = api_token.strip()

        banner(f"Connect Zabbix {self.zbxname}", bottom_text="")

        while True:
            try:
                if api_token:
                    self.login(api_token=api_token)
                else:
                    username, passwd = get_user_passwd(self.zbxname)
                    self.login(username, passwd)

                print(
                    f"Connected to Zabbix {self.zbxname} API Version {self.api_version()}."
                )
                self.__zbx_version = float(self.api_version()[:3])
                sleep(1)
                break
            except ZabbixAPIException as error:
                os.system("cls" if os.name == "nt" else "clear")
                if "name or password" in str(error):
                    print("[ERROR] Login name or password is incorrect")
                elif "Not Found for url" in str(error):
                    print("[ERROR] Not Found for url")
                    self.server = get_url()
                elif "Invalid URL" in str(error):
                    print("[ERROR] " + str(error))
                    self.server = get_url(self.zbxname)
                elif "Failed to establish a new connection" in str(error):
                    print(
                        f"[ERROR] Failed to establish a new connection `{self.server}`."
                    )
                    self.server = get_url(self.zbxname)
                else:
                    print("here")
                    print(type(error).__name__, error)
                    sys.exit(1)
            except Exception as error:
                if type(error).__name__ == "MissingSchema":
                    print(error)
                    self.server = get_url(self.zbxname)
                elif type(error).__name__ == "ConnectionError":
                    print("Connection error: Enter the correct URL")
                    self.server = get_url(self.zbxname)
                else:
                    print(f"[ERRO] {type(error).__name__}: {error}")
                    sys.exit(1)

    def parms_get_hosts(
        self,
        search: dict | None = {},
        filters: dict | None = {},
        **kwargs,
    ) -> dict:
        parms = {
            "output": [
                "host",
                "name",
                "status",
                "proxy_hostid",
                "proxyid",
            ],
            "selectParentTemplates": ["name"],
            "selectTags": ["tag", "value"],
            "selectMacros": ["macro", "value"],
            "searchByAny": True,
            "sortfild": ["name"],
            "sortorder": "DESC",
            "search": search,
            "filter": filters,
            **kwargs,
        }

        if self.__zbx_version > 6:
            parms["selectHostGroups"] = ["name", "groupid"]  # Zabbix >=6.0
        else:
            parms["selectGroups"] = ["name", "groupid"]  # Zabbix <=6.0

        return parms

    def get_hosts(self, **parms) -> dict:
        hosts = dict()
        count = 0
        while True:
            try:
                result = self.host.get(**parms)
                for host in result:
                    info = self._host_info(**host)
                    hosts[host["hostid"]] = info

                # hosts = {
                #     host["hostid"] :  host_info(**host) for host in result
                # }

                break
            except Exception as error:
                print(error)
                count += 1
                if count >= 10:
                    print("Failed to collect information")
                    break
                sleep(2)

        return hosts

    def _host_info(self, delimiter=",", **host_get_return: dict) -> dict:
        host = {
            "hostid": host_get_return["hostid"],
            "host": host_get_return["host"],
            "name": host_get_return["name"],
            "status": "enabled" if host_get_return["status"] == "0" else "disabled",
            "proxyid": host_get_return.get("proxy_hostid")
            or host_get_return.get("proxyid"),
            # "tags": "",
            # "macros": "",
        }

        templates = [i["name"] for i in host_get_return["parentTemplates"]]
        host["templates"] = delimiter.join(templates)

        if host_get_return.get("hostgroups"):
            groups = [i["name"] for i in host_get_return["hostgroups"]]
        else:
            groups = [i["name"] for i in host_get_return["groups"]]  # Zabbix <=6.0
        host["hostgroups"] = delimiter.join(groups)

        macros = []
        for macro in host_get_return["macros"]:
            macros.append(f"{macro['macro']}={macro['value']}")
        host["macros"] = delimiter.join(macros)

        tags = []
        for tag in host_get_return["tags"]:
            tags.append(f"{tag['tag']}={tag['value']}")
        host["tags"] = delimiter.join(tags)

        return host

    def get_interface(self, get_hosts_return: dict["hostid":dict]) -> None:
        hosts = get_hosts_return
        hostid_list = [*hosts.keys()]
        count = 0
        while True:
            try:
                _result = self.hostinterface.get(
                    hostids=hostid_list,
                    output=["hostid", "ip", "dns"],
                )

                for i in _result:
                    ip = i["ip"] if bool(i["ip"]) else i["dns"]
                    hosts[i["hostid"]]["ip"] = ip if ip else 0
                break
            except Exception as error:
                print(error)
                count += 1
                if count > 10:
                    print("Failed to collect information")
                    break
                sleep(2)
        # return hosts

    def get_month_problems(
        self,
        host: dict,
        month: int | None = 0,
        year: int | None = 0,
        alert_name: str = "Unavailable by ICMP ping",
    ) -> dict[dict]:
        host = host
        hostid = host["hostid"]
        month = int(month) or datetime.now().month
        year = int(year) or datetime.now().year
        alert_name = alert_name

        time_from, time_till, *_ = get_date_month(month, year)

        count = 0
        while True:
            try:
                problems_result = self.event.get(
                    hostids=hostid,
                    output=[
                        "name",
                        "clock",
                        "r_eventid",
                        "acknowledged",
                        "value",
                        "object",
                        "objectid",
                    ],
                    select_acknowledges=["message"],
                    problem_time_from=time_from,
                    problem_time_till=time_till,
                    value=1,
                    # sortfild="clock",
                    # sortorder="DESC",
                    search={"name": alert_name},
                )
                break
            except Exception as error:
                print(error)
                count += 1
                if count > 20:
                    problems_result = []
                    print("Failed to collect information host:", host["name"])
                    break
                sleep(2)

        problems = dict()
        for problem in problems_result:
            clock = (
                problem["clock"] if int(problem["clock"]) >= time_from else time_from
            )

            messages = []
            for e in problem["acknowledges"]:
                msg = ""
                if e.get("message"):
                    msg = e["message"].strip().replace("\n", "/")
                    msg = msg.replace("\r", "/")
                    # msg = msg.replace(",", " | ")
                messages.append(msg)

            messages_join = "||".join(messages)

            info = {
                "host": host["name"],
                "hostid": hostid,
                "eventid": problem["eventid"],
                "name": problem["name"],
                "hostid": hostid,
                "clock": str(clock),
                "r_eventid": problem["r_eventid"],
                "ack": problem["acknowledged"],
                "messages": messages_join,
                "value": problem["value"],
            }

            problems[problem["eventid"]] = info
        return problems

    def get_month_problems_resolved(
        self,
        host: dict,
        month: int | None = 0,
        year: int | None = 0,
        alert_name: str = "Unavailable by ICMP ping",
    ) -> dict[dict]:
        host = host
        hostid = host["hostid"]
        month = int(month) or datetime.now().month
        year = int(year) or datetime.now().year
        alert_name = alert_name

        time_from, time_till, *_ = get_date_month(month, year)

        count = 0
        while True:
            try:
                _problems_result = self.event.get(
                    hostids=hostid,
                    output=["name", "clock", "value", "object", "objectid"],
                    # select_acknowledges=["message"],
                    problem_time_from=time_from,
                    problem_time_till=time_till,
                    value=0,
                    # sortfild="clock",
                    # sortorder="DESC",
                    search={"name": alert_name},
                )
                break
            except Exception as error:
                print(error)
                count += 1
                if count > 20:
                    _problems_result = []
                    print("Failed to collect information host:", host["name"])
                    break
                sleep(2)

        problems_resolved = dict()
        for problem in _problems_result:
            problems_resolved[problem["eventid"]] = problem

        return problems_resolved

    def get_month_events(
        self,
        hostid: str,
        month: int | None = 0,
        year: int | None = 0,
        alert_name: str = "",
    ) -> list[dict]:
        hostid = hostid
        month = int(month) or datetime.now().month
        year = int(year) or datetime.now().year
        alert_name = alert_name

        time_from, time_till, *_ = get_date_month(month, year)

        events = []
        count = 0
        while True:
            try:
                event_results = self.event.get(
                    hostids=hostid,
                    output=["name", "clock", "r_eventid", "acknowledged", "value"],
                    select_acknowledges=["message"],
                    time_from=time_from,
                    time_till=time_till,
                    search={"name": alert_name},
                    sortfild=["clock"],
                    sortorder="DESC",
                    value="1",
                )
                break

            except Exception as error:
                print(error)
                count += 1
                if count >= 10:
                    print("Falha ao tentar coletar info: hostid", hostid)
                    event_results = []
                    break
                asyncio.sleep(2)

        if len(event_results) > 0:
            for event in event_results:
                messages = []
                for e in event["acknowledges"]:
                    msg = ""
                    if e.get("message"):
                        msg = e["message"].strip().replace("\n", "/")
                        msg = msg.replace("\r", "/")
                        # msg = msg.replace(",", " | ")
                    messages.append(msg)

                messages_join = "||".join(messages)
                clock = int(event["clock"])
                info = {
                    "hostid": hostid,
                    "name": event["name"],
                    "hostid": hostid,
                    "clock": clock,
                    "r_eventid": event["r_eventid"],
                    "ack": event["acknowledged"],
                    "messages": messages_join,
                }

                events.append(info)
        return events

    def get_month_resolved_events(
        self,
        hostid: str,
        month: int | None = 0,
        year: int | None = 0,
        alert_name: str = "",
    ) -> dict:
        hostid = hostid
        month = int(month) or datetime.now().month
        year = int(year) or datetime.now().year
        alert_name = alert_name

        time_from, time_till, *_ = get_date_month(month, year)

        events = dict()
        count = 0
        while True:
            try:
                event_results = self.event.get(
                    hostids=hostid,
                    output=["name", "clock", "eventid", "acknowledged", "value"],
                    select_acknowledges=["message"],
                    time_from=time_from,
                    time_till=time_till,
                    search={"name": alert_name},
                    sortfild=["clock"],
                    sortorder="DESC",
                    value="0",
                )
                break

            except Exception as error:
                print(error)
                count += 1
                if count >= 10:
                    print("Falha ao tentar coletar info: hostid", hostid)
                    event_results = []
                    break
                sleep(2)

        if len(event_results) > 0:
            print("aqui")
            for event in event_results:
                messages = []
                for e in event["acknowledges"]:
                    msg = ""
                    if e.get("message"):
                        msg = e["message"].strip().replace("\n", "/")
                        msg = msg.replace("\r", "/")
                        # msg = msg.replace(",", " | ")
                    messages.append(msg)

                messages_join = "||".join(messages)
                clock = int(event["clock"])
                events[event["eventid"]] = {
                    "hostid": hostid,
                    "name": event["name"],
                    "hostid": hostid,
                    "clock": clock,
                    "eventid": event["eventid"],
                    "ack": event["acknowledged"],
                    "messages": messages_join,
                }

        return events

    def get_event_resolved(self, event):
        r_clock = 0
        if event.get("r_eventid") != "0" and event.get("r_eventid") is not None:
            count = 0
            while True:
                try:
                    get_resolved_result = self.event.get(
                        eventids=event["r_eventid"],
                        output=["clock"],
                    )
                    if len(get_resolved_result) > 0:
                        r_clock = get_resolved_result[0]["clock"]
                    break

                except Exception as error:
                    print(error)
                    count += 1

                    if count >= 60:
                        print(
                            "Falha ao tentar coletar info: enventid", event["r_eventid"]
                        )
                        break
                    asyncio.sleep(2)

        delta = int(r_clock) - int(event["clock"]) if r_clock != 0 else 0
        event["r_clock"] = r_clock
        event["duration"] = delta
