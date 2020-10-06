#!/usr/local/bin/python


# import sys
import os
import csv
import ldap
import argparse
import yaml
from textwrap import wrap
from datetime import datetime, timezone
from collections import ChainMap
from dotenv import load_dotenv
from libnmap.process import NmapProcess
from libnmap.parser import NmapParser, NmapParserException
load_dotenv()
config = yaml.safe_load(open("config.yaml"))

parser = argparse.ArgumentParser(description='Process CrashPlan report CSV')
parser.add_argument('filename', type=str, help='CrashPlan CSV to be processed')
parser.add_argument('--full', action='store_true')

args = parser.parse_args()
filename = args.filename
full = args.full

print(config)

new_columns = {
    "backupCompletePercentage": "complete",
    "lastConnectedDate": "lastConnected",
    "lastCompletedBackupDate": "lastCompleted"
}

windows_versions = {
    "5.1": "XP",
    "5.2": "XP",
    "6.0": "Vista",
    "6.1": "7",
    "6.2": "8",
    "6.3": "8.1",
    "10.0": "10"
}

columns = [
    # "roomNumber",
    "network",
    "title",
    "notes",
    "phone",
    "cn",
    "username",
    "version",
    "lastCompleted",
    "alertStates",
    "lastConnected",
    "complete",
    "osVersion",
    "creationDate",
    "lastActivity",
    "deviceName",
    "deviceOsHostname",
    "address",
    "remoteAddress",
    "selectedBytes",
    "archiveBytes",
    "deviceUid"
]


time_columns = [
    "creationDate",
    "lastConnected",
    "lastCompleted",
    "lastActivity"
]

size_columns = ["selectedBytes", "archiveBytes"]
allowed_versions = ["7.0.3.55", "6.8.8.12"]
critical_alert = "CriticalBackupAlert"
warning_alert = "WarningBackupAlert"
now = datetime.now(timezone.utc)

# via a .env file with format 'FCP_jfrancos=33-555':
roomNumber_overrides = {key[4:]: value for (key, value) in dict(
    os.environ).items() if key.startswith('FCP_')}


def ldap_search(uids, attrs):
    ldap_limit = 100
    ldap_db = ldap.initialize("ldaps://ldap.mit.edu:636")
    chunked_uids = [uids[i:i + ldap_limit]
                    for i in range(0, len(uids), ldap_limit)]
    result = []
    for uid_chunk in chunked_uids:
        print(f"Querying ldap server for {len(uid_chunk)} kerberos ids")
        filter = "(|(uid=" + ")(uid=".join(uid_chunk) + "))"
        result += ldap_db.search_s(
            "dc=mit,dc=edu",
            ldap.SCOPE_SUBTREE,
            filter,
            set(attrs + ['uid'])
        )
    result = [item[1] for item in result]
    result = [{key: os.linesep.join([item.decode() for item in value])
               for (key, value) in userdict.items()} for userdict in result]
    result = [{item['uid']:item} for item in result]
    return dict(ChainMap(*result))


def add_ldap(row, ldap_dict):
    max_width = 27
    user = ldap_dict[row['username']]
    phone = user.get('telephoneNumber')
    cn = user.get('cn')
    title = user.get('title')
    if title:
        title = os.linesep.join(wrap(title, width=max_width))
    return {'title': title, 'phone': phone, 'cn': cn, **row}
    # room_number = roomNumber_overrides.get(
    #     row['username']) or user.get('roomNumber')
    # return {'roomNumber': room_number, 'cn': user.get('cn'), **row}


def fix_size(row):
    def format(value):
        new_value = 0 if value == "null" else value
        new_value = int(new_value) / 2 ** 10 / 2 ** 10
        new_value = round(new_value)
        new_value = f'{new_value:,}' + " MB"
        return new_value
    return {**row, **{key: format(value)
                      for (key, value) in row.items() if key in size_columns}}


def remove_extraneous_columns(row):
    return {key: value for (key, value) in row.items() if key in columns}


def fix_time(row):
    def truncate_time(value):
        split_time = value.split()
        if len(split_time) > 0 and "*" not in split_time[0]:
            split_time[0] = value[:10]
        return " ".join(split_time)
    return {**row, **{key: truncate_time(value)
                      for (key, value) in row.items() if key in time_columns}}


def flag_issues(row):
    flag_dict = {**row}

    def flag(key, severity):
        flag_dict[key] = row[key] + " " + "*" * severity
    row['version'] not in allowed_versions and flag('version', 2)
    row['alertStates'] == critical_alert and flag('alertStates', 2)
    row['alertStates'] == warning_alert and flag('alertStates', 1)
    try:
        most_recent = datetime.fromisoformat(row['lastCompleted'])
        (now - most_recent).days > 7 and flag(
            'lastCompleted', 1)
    except ValueError:
        flag('lastCompleted', 1)
    if flag_dict != row or full:
        return flag_dict


def add_percents(row):
    try:
        float(row['complete'])
        return {**row, 'complete': row['complete'] + " %"}
    except ValueError:
        return row


def abbreviate_alerts(row):
    split = row['alertStates'].split()
    if len(split) == 1:
        return row
    return {**row, 'alertStates': split[0][:-11] + " " + split[1]}


def translate_osver(row):
    if row['os'] == 'win':
        return {**row, 'osVersion':
                'Windows ' + windows_versions[row['osVersion']]}
    elif row['os'] == 'mac' and row['osVersion'].startswith('10.'):
        return {**row, 'osVersion':
                'macOS ' + row['osVersion']}
    else:
        return row


def abbreviate_archive_names(row):
    max_width = 20
    new_names = {}
    for name in ['deviceName', 'deviceOsHostname']:
        new_names[name] = os.linesep.join(wrap(row[name], width=max_width))
    return {**row, **new_names}


def add_network(row, rdp_list):
    address = row['remoteAddress']
    network = ''
    if address.startswith('18.28') or address.startswith('18.30'):
        network = 'VPN'
    elif address.startswith('18.') or address.startswith('10.'):
        network = 'MITnet'
        if (address in rdp_list):
            network += ' / RDP'
    else:
        network = 'External'
    return {**row, 'network': network}


def add_notes(row):
    for key in [key for key in config.keys() if row.get(key)]:
        uid = row[key]
        if uid in config[key]:
            return {**row, 'notes': config[key][uid]}
        elif int(uid) in config[key]:
            return {**row, 'notes': config[key][int(uid)]}
    if row['network'] == 'MITnet' and row['username'] not in config['on_campus']:
        return {**row, 'notes': "user not on campus"}
    else:
        return row


def get_rdp(reader):
    ips = [row['remoteAddress'].split(':')[0] for row in reader]
    rdp_candidates = [
        ip for ip in ips if     # is on MITnet
        (ip.startswith('10.') or ip.startswith('18.'))
        and not                 # and not on VPN
        (ip.startswith('18.28') or ip.startswith('18.30'))
    ]
    print(f"Nmap scanning {len(rdp_candidates)} ips")
    nmap_options = '-np 3389 -Pn -T5'
    nm = NmapProcess(rdp_candidates, nmap_options)
    nm.run()
    report = NmapParser.parse(nm.stdout)
    return [host.address for host in report.hosts if host.get_open_ports()]


new_list = []
with open(filename, 'r', newline='') as input_file:
    line = input_file.readline()
    fieldnames = [new_columns.get(name) or name for name in line.split(",")]
    reader = list(csv.DictReader(input_file, fieldnames=fieldnames))
    users = list(set([row['username'] for row in reader]))
    rdp_list = get_rdp(reader)

    ldap_dict = ldap_search(users, [
        'cn',
        # 'roomNumber',
        'telephoneNumber',
        'title'
    ])
    for row in reader:
        new_row = flag_issues(row)
        if not new_row:
            continue
        new_row = translate_osver(new_row)
        new_row = fix_time(new_row)
        new_row = fix_size(new_row)
        new_row = add_ldap(new_row, ldap_dict)
        new_row = add_percents(new_row)
        new_row = abbreviate_alerts(new_row)
        new_row = abbreviate_archive_names(new_row)
        new_row = add_network(new_row, rdp_list)
        new_row = add_notes(new_row)
        new_row = remove_extraneous_columns(new_row)
        new_list.append(new_row)


def sort_order(row):
    values = [str(value) for value in row.values()]
    joined_values = "".join(values)
    num_asterisks = joined_values.count("*")
    return (-num_asterisks)
    # room_number = str(row['roomNumber'])
    # return (-num_asterisks, room_number)


new_list.sort(key=sort_order)

with open(filename[:-4] + '-fixed.csv', 'w', newline='') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=columns)
    writer.writeheader()
    for row in new_list:
        writer.writerow(row)
