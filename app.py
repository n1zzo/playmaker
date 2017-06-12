from googleplay_api.googleplay import GooglePlayAPI, LoginError
from google.protobuf.message import DecodeError

import configparser
import urllib.request
from urllib.error import URLError
import os
import sys
import json


def get_token(config):
    print('Retrieving token from %s' % config['Main']['tokenurl'])
    r = urllib.request.urlopen(config['Main']['tokenurl'])
    token = r.read().decode('utf-8')
    config['Main']['token'] = token
    return token


class Play(object):
    def __init__(self):
        self.config = configparser.ConfigParser()
        config_paths = [
            os.path.expanduser('~') + '/.config/playmaker.conf',
            '/etc/playmaker.conf',
            'playmaker.conf'
        ]
        while not os.path.isfile(config_paths[0]):
            config_paths.pop(0)
            if len(config_paths) == 0:
                raise OSError('No configuration file found')
                sys.exit(1)
        self.config.read(config_paths[0])
        self.set_download_folder('.')
        self.service = GooglePlayAPI(self.config['Main']['id'], 'en_US', True)
        if self.config['Main']['token'] == '':
            try:
                for i in range(1, 4):
                    print('#%d try' % i)
                    token = get_token(self.config)
                    if token == "":
                        continue
                    else:
                        break
                if token == "":
                    raise LoginError()
                    sys.exit(1)
                self.service.login(None, None, token)
            except URLError:
                print('Failed to fetch url, try again in a few minutes')
                sys.exit(1)
            except LoginError:
                print('Login failed')
                sys.exit(1)
        else:
            try:
                self.service.login(None, None, self.config['Main']['token'])
            except LoginError:
                print('Login failed')
                sys.exit(1)

    def search(self, appName, numItems=5):
        results = self.service.search(appName, numItems, None).doc
        all_apps = []
        if len(results) > 0:
            results = results[0].child
        else:
            return "[]"
        for result in results:
            if result.offer[0].checkoutFlowRequired:
                continue
            appDetails = result.details.appDetails
            app = {
                'title': result.title,
                'developer': result.creator,
                'version': appDetails.versionCode,
                'size': self.file_size(appDetails.installationSize),
                'docId': result.docid,
                'numDownloads': appDetails.numDownloads,
                'uploadDate': appDetails.uploadDate,
                'stars': '%.2f' % result.aggregateRating.starRating
            }
            all_apps.append(app)
        return json.dumps(all_apps)

    def set_download_folder(self, folder):
        self.config['Main']['download_path'] = folder

    def file_size(self, num):
        for x in ['bytes', 'KB', 'MB', 'GB', 'TB']:
            if num < 1024.0:
                return "%3.1f%s" % (num, x)
            num /= 1024.0

    def get_bulk_details(self, apksList):
        try:
            results = self.service.bulkDetails(apksList)
        except DecodeError:
            print('Cannot decode data')
            return {}
        details = dict()
        for pos, apk in enumerate(apksList):
            current = results.entry[pos]
            doc = current.doc
            appDetails = doc.details.appDetails
            if any([
                appDetails.uploadDate == '',
                doc.docid == '',
                doc.title == ''
            ]):
                # no result found, so we avoid creating the entry
                continue
            details[apk] = {
               'title': doc.title,
               'developer': doc.creator,
               'size': self.file_size(appDetails.installationSize),
               'numDownloads': appDetails.numDownloads,
               'uploadDate': appDetails.uploadDate,
               'docId': doc.docid,
               'version': str(appDetails.versionCode),
               'stars': '%.2f' % doc.aggregateRating.starRating
            }
        return details

    def download_selection(self, apksList):
        success = list()
        failed = list()
        unavail = list()

        downloadPath = self.config['Main']['download_path']
        if not os.path.isdir(downloadPath):
            os.mkdir(downloadPath)
        details = self.get_bulk_details(apksList)
        for appname, appdetails in details.items():
            print(appdetails)
