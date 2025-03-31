#!/usr/bin/env python3

import sys
import os, csv
from datetime import datetime
from modules.get_csv import csv_to_list
from modules.gets import get_url, get_user_passwd
from modules.zbx import zbx_connect
from modules.banner import banner
# Variavbles

path = os.path.abspath(os.path.dirname(__file__))
filename = "create_users.csv"
file_url = "file_url.csv"


def zbx_user_create(zapi, users_list: list):
    result = dict()
    zbx_version = zapi.api_version()[:3]

    for user in users_list:
        fullname = user[0].strip().split()
        email = user[1].strip().lower()
        user_role = user[2].strip()
        user_group = user[3].strip()

        username = email.split("@")[0] if "@alloha.com" in email else email
        passwd = (
            f"{username[:2].lower()}"
            f"{len(email):>02}"
            f"{username.split('.')[1][:3].upper() if len(username.split('.')) > 1  else username[-3:].upper()}"
            f"{len(user[0]):>02}"
            "#Mudar"
        )

        usr = {
            "passwd": passwd,
            "autologin": 1,
            "autologout": "0",
            "refresh": "2m",
        }
        
        if len(fullname) <= 2 and len(fullname[1]) < 5:
            usr["name"] = " ".join(fullname).title()
        else:
            usr["name"] = fullname[0].title()
            usr["surname"] = " ".join(fullname[1:]).title()

        if username not in result:
            result[username] = {}
        if float(zbx_version) >= 6:
            already_exist = zapi.user.get(filter={"username": username})
            role = zapi.role.get(filter={"name": user_role})
        else:
            already_exist = zapi.user.get(filter={"alias": username})
            if float(zbx_version) >= 5.2:
                role = zapi.role.get(filter={"name": user_role})

        usrgrp = zapi.usergroup.get(filter={"name": user_group})

        result[username]["fullname"] = " ".join(fullname).title()

        if already_exist != []:
            print(f"User `{username}` already registered")
            result[username]["result"] = "existing"
        elif float(zbx_version) >= 5.2 and role == []:
            result[username]["result"] = "unknown role"
            print(f"Unknown `{user_role}` role.")
        elif usrgrp == []:
            result[username]["result"] = "unknown group"
            print(f"Unknown `{user_group}` group.")
        else:
            if float(zbx_version) < 6:
                usr["alias"] = username
            else:
                usr["username"] = username

            if float(zbx_version) >= 5.2:
                usr["roleid"] = role[0]["roleid"]

            if float(zbx_version) >= 5.2:
                usr["medias"] = [{"mediatypeid": "1", "sendto": [email]}]
            else:
                usr["user_medias"] = [{"mediatypeid": "1", "sendto": [email]}]

            usr["usrgrps"] = [{"usrgrpid": usrgrp[0]["usrgrpid"]}]
            zapi.user.create(usr)
            result[username]["password"] = passwd
            result[username]["result"] = "success"
            print(f" Successfully created user `{username}`.")

    return result


file_csv = os.path.join(path, filename)
# file_url = os.path.join(path, file_url)

try:
    users_list = csv_to_list(file_csv)
except FileNotFoundError as e:
    print(str(e))
    sys.exit(1)

try:
    url_list = csv_to_list(file_url)
except FileNotFoundError:
    url = get_url()
    url_list = [("unknown", url)]
except Exception as error:
    print(error)
    sys.exit(1)

result = dict()
list_result = [["name", "user", "password"]]
users = dict()

for zbx_srv in url_list:
    zapi = zbx_connect(*zbx_srv)
    resp = zbx_user_create(zapi, users_list)
    result[zbx_srv[0]] = resp

for server, users_info in result.items():
    list_result[0].append(server)
    for user, info in users_info.items():
        if user in users:
            users[user]["result"].append(info["result"])
            if info.get("password") is not None:
                users[user]["passwd"] = info["password"]
        else:
            users[user] = {
                "name": info.get("fullname"),
                "passwd": info.get("password"),
                "result": [info["result"]],
            }

for user, info in users.items():
    list_result.append(
        (
            info["name"],
            user,
            info["passwd"] if info["passwd"] else "N/A",
            *info["result"],
        )
    )

today = datetime.strftime(datetime.now(), "%Y-%m-%d_%H-%M")
file_result = os.path.join(path, f"user_created_result_{today}.csv")

with open(file_result, "w", encoding="utf-8") as file_:
    file_csv = csv.writer(file_, lineterminator="\n")
    for item in list_result:
        file_csv.writerow(item)
