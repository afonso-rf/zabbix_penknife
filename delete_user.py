#!/usr/bin/env python3
# %%
import os
import sys, csv
from pyzabbix import ZabbixAPI
from pprint import pprint as pp
from datetime import datetime
from modules.get_csv import csv_to_list
from modules.gets import get_user_passwd

# %%
# Variavbles

path = os.curdir
filename = "delete_users.csv"
file_url = "file_url.csv"

arguments = sys.argv[1:]  # TODO: Tratar exceptions
# if arguments:
#     filename = arguments[0]

file_csv = os.path.join(path, filename)
# file_url = os.path.join(path, file_url)


# %%
# TODO: Tratar erro de user/senha
def zbx_user_delete(users_list: list, url: str, api_token=None):
    username = ""
    passwd = ""
    # Zabbix connect
    zapi = ZabbixAPI(url)
    while True:
        if api_token:
            zapi.login(api_token=api_token)
            break
        elif username and passwd:
            zapi.login(username, passwd)
            break
        else:
            username, passwd = get_user_passwd()

    pp(f"Connected to Zabbix API Version {zapi.api_version()}.")

    result = dict()
    zbx_version = zapi.api_version()[:3]

    for user in users_list:
        fullname = user[0].strip()
        email = user[1].strip().lower()
        username = email.split("@")[0] if "@alloha.com" in email else email

        if username not in result:
            result[username] = {}
            result[username]["name"] = fullname
        if float(zbx_version) >= 6:
            exist = zapi.user.get(filter={"username": username})
        else:
            exist = zapi.user.get(filter={"alias": username})

        if exist == []:
            pp(f"User `{username}` unknown")
            result[username]["result"] = "unknown"
        else:
            try:
                zapi.user.delete(exist[0]["userid"])
                result[username]["result"] = "deleted"
                pp(f" Successfully deleted user `{username}`.")
            except Exception as error:
                if 'No permissions to call "user.delete"' in str(error):
                    print("Zabbix User no permissions to delete")
                    result[username]["result"] = "Zbx User no permissions to delete"

    return result


# %%
users_list = csv_to_list(file_csv)
url_servers = csv_to_list(file_url)

# %%
result = dict()
for info in url_servers:
    try:
        if info[0]:
            if "/" not in info[0]:
                server_name = info[0].upper()
            else:
                server_name = "name error"
        else:
            server_name = "Unknown"
    except IndexError:
        server_name = "Unknown"

    try:
        if info[1]:
            if "//" in info[1]:
                url = info[1]
            else:
                url = "url error"
        else:
            url = "Unknown"
    except IndexError:
        url = "Unknown"

    try:
        if info[2]:
            api_token = info[2]
        else:
            api_token = ""
    except IndexError:
        api_token = ""

    print(f"Deleting users in Zabbix {server_name}.")
    # TODO: Adicionar testes de conexão no Zabbix
    resp = zbx_user_delete(users_list, url, api_token)
    result[server_name] = resp

# %%
resp = dict()
result_list = []
servernames = []
for serv, users in result.items():
    servernames.append(serv)
    for user, info in users.items():
        exist = 0
        for item in result_list:
            if item[1] == user:
                item.append(info["result"])
                exist = 1
                break
        if not exist:
            result_list.append([info["name"], user, info["result"]])

# %%
today = datetime.strftime(datetime.now(), "%Y-%m-%d_%H-%M")
file_result = os.path.join(path, f"delete_result_{today}.csv")
with open(file_result, "w", encoding="UTF-8") as file_:
    file_.write("name,username," + ",".join(servernames) + "\n")
    for item in result_list:
        file_.write(",".join(item) + "\n")
