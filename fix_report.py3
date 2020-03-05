#!/usr/bin/python3

import sys
import csv
import ldap
from datetime import datetime, timezone
from collections import ChainMap

columns = ["cn", "roomNumber",
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
				"lastActivity"]

size_columns = ["selectedBytes", "archiveBytes"]
allowed_versions = ["7.0.3.55", "6.8.8.12"]
critical_alert = "CriticalBackupAlert"
warning_alert = "WarningBackupAlert"

filename = sys.argv[1]
now = datetime.now(timezone.utc)

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
		new_value = int(new_value) / 2 ** 10 / 2 ** 10
		new_value = round(new_value)
		new_value = f'{new_value:,}' + " MB"
		return new_value
	return {**row, **{key: format(value) for (key, value) in row.items() if key in size_columns}}


def remove_extraneous_columns(row):
	return {key: value for (key, value) in row.items() if key in columns}


def fix_time(row):
	def truncate_time(value):
		split_time = value.split()
		if len(split_time) > 0 and "*" not in split_time[0]:
			split_time[0] = value[:10]
		return " ".join(split_time)
	return {**row, **{key: truncate_time(value) for (key, value) in row.items() if key in time_columns}}


def print_csv(reader):
	for row in reader:
		print(row)

def punctuate_issues(row):
	punct_dict = {**row}
	def punctuate(key, severity):
		punct_dict[key] = row[key] + " " + "*" * severity
	row['version'] not in allowed_versions 	and punctuate('version', 2)
	row['alertStates'] == critical_alert 	and punctuate('alertStates', 2)
	row['alertStates'] == warning_alert		and punctuate('alertStates', 1)
	try:
		last_completed = datetime.fromisoformat(row['lastCompletedBackupDate'])
		((now - last_completed).days > 7)	and punctuate('lastCompletedBackupDate', 3)
	except:
		punctuate('lastCompletedBackupDate', 1)
	if punct_dict != row:
		return punct_dict

with open(filename, 'r', newline='') as input_file:
	reader = list(csv.DictReader(input_file))
	users = list(set([row['username'] for row in reader]))
	ldap_dict = ldap_search(users, ['cn', 'roomNumber'])
	with open('fixed.csv', 'w', newline='') as csvfile:
		writer = csv.DictWriter(csvfile, fieldnames=columns)
		writer.writeheader()
		for row in reader:
			new_row = punctuate_issues(row)
			# if not new_row:
			# 	continue
			new_row = remove_extraneous_columns(new_row)
			new_row = fix_time(new_row)
			new_row = fix_size(new_row)
			new_row = add_ldap(new_row, ldap_dict)
			writer.writerow(new_row)