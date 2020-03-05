#!/usr/bin/python3

import sys
import csv
import ldap
from collections import ChainMap

columns = ["roomNumber",
           "cn",
           "username",
           "deviceName",
           "deviceOsHostname",
           "version",
           "alertStates",
           "os",
           "osVersion",
           "address",
           "remoteAddress",
           "creationDate",
           "selectedBytes",
           "backupCompletePercentage",
           "archiveBytes",
           "lastConnectedDate",
           "lastCompletedBackupDate",
           "lastActivity"]

time_columns = ["creationDate",
                "lastConnectedDate",
                "lastCompletedBackupDate",
                "lastActivity"
                ]

size_columns = ["selectedBytes", "archiveBytes"]

filename = sys.argv[1]
new_report = []


def ldap_search(uids, attrs):
    ldap_limit = 100
    ldap_db = ldap.initialize("ldaps://ldap.mit.edu:636")
    chunked_uids = [uids[i:i + ldap_limit]
                    for i in range(0, len(uids), ldap_limit)]
    result = []
    for uid_chunk in chunked_uids:
        print(f"querying ldap server for {len(uid_chunk)} kerbs")
        filter = "(|(uid=" + ")(uid=".join(uid_chunk) + "))"
        result += ldap_db.search_s("dc=mit,dc=edu",
                                   ldap.SCOPE_SUBTREE, filter, set(attrs + ['uid']))
    result = [item[1] for item in result]
    result = [{key: " / ".join([item.decode() for item in value])
               for (key, value) in userdict.items()} for userdict in result]
    result = [{item['uid']:item} for item in result]
    return dict(ChainMap(*result))


def add_ldap(row, ldap_dict):
    user = ldap_dict[row['username']]
    return {'roomNumber': user.get('roomNumber'), 'cn': user.get('cn'), **row}


def fix_size(row):
    def format(value):
        new_value = 0 if value == "null" else value
        new_value = int(new_value) / 1024 / 1024
        new_value = round(new_value)
        new_value = f'{new_value:,}' + " MB"
        return new_value
    return {**row, **{key: format(value) for (key, value) in row.items() if key in size_columns}} # i think this can be consolidated???


def remove_extraneous_columns(row):
    return {key: value for (key, value) in row.items() if key in columns}


def fix_time(row):
    return {**row, **{key: value[:10] for (key, value) in row.items() if key in time_columns}}


def print_csv(reader):
    for row in reader:
        print(row)


with open(filename, 'r', newline='') as input_file:
    reader = list(csv.DictReader(input_file))
    users = list(set([row['username'] for row in reader]))
    ldap_dict = ldap_search(users, ['cn', 'roomNumber'])
    with open('fixed.csv', 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=columns)
        writer.writeheader()
        for row in reader:
            new_row = remove_extraneous_columns(row)
            new_row = fix_time(new_row)
            new_row = fix_size(new_row)
            new_row = add_ldap(new_row, ldap_dict)
            # new_report.append(new_row)
            writer.writerow(new_row)
