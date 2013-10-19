import sublime
import sublime_plugin

import json
import os
import sys
import threading
import urllib.request
import webbrowser

from .thread_progress import ThreadProgress


def plugin_loaded():
    global BASE_URL
    global HEADERS
    global qiita_user
    global qiita_token

    BASE_URL = 'https://qiita.com/api/v1'
    HEADERS = {"Accept": "application/json", "Content-type": "application/json"}

    settings = sublime.load_settings('Qiita.sublime-settings')
    qiita_user = settings.get('username')
    qiita_token = settings.get('token')


def api_request(url_or_request):
    res = urllib.request.urlopen(url_or_request)
    encoding = res.headers.get_content_charset()
    return json.loads(res.read().decode(encoding))


class QiitaCommandBase(sublime_plugin.WindowCommand):

    def __init__(self, window):
        self.window = window

    def qiita_item(self):
        return self.window.active_view().settings().get('qiita_item')


class QiitaPostNewItemCommand(QiitaCommandBase):

    def run(self):
        thread = PostNewItemThread(self.window)
        thread.start()
        ThreadProgress(thread, 'Post new item to qiita', 'Done.')

    def is_enabled(self):
        return self.qiita_item() == None or self.qiita_item().get('url') == None


class QiitaGetItemsCommand(QiitaCommandBase):

    def run(self):
        thread = GetItemsThread(self.window)
        thread.start()
        ThreadProgress(thread, 'Geting item list from qiita', 'Done.')


class QiitaUpdateItemCommand(QiitaCommandBase):

    def run(self):
        uuid = self.qiita_item().get('uuid')
        thread = UpdateItemThread(self.window, uuid)
        thread.start()
        ThreadProgress(thread, 'Update item to qiita', 'Done.')

    def is_enabled(self):
        return self.qiita_item() != None and self.qiita_item().get('url') != None


class QiitaOpenItemUrlCommand(QiitaCommandBase):

    def run(self):
        webbrowser.open_new_tab(self.qiita_item().get('url'))

    def is_enabled(self):
        return self.qiita_item() != None and self.qiita_item().get('url') != None


class QiitaShowItemInfo(QiitaCommandBase):

    def run(self):
        str = "uuid: %s \nurl: %s" % (self.qiita_item().get('uuid'), self.qiita_item().get('url'))
        sublime.message_dialog(str)

    def is_enabled(self):
        return self.qiita_item() != None and self.qiita_item().get('url') != None

class PostNewItemThread(threading.Thread):

    def __init__(self, window):
        self.window = window
        threading.Thread.__init__(self)

    def run(self):
        data = self.get_item_data()
        url = BASE_URL + '/items?token=%s' % qiita_token

        req = urllib.request.Request(url, data, HEADERS)
        res = api_request(req)

        webbrowser.open_new_tab(res.get('url'))

    def get_item_data(self):
        item_data = {}

        # TODO: sample data
        item_data['title'] = 'sublime post'
        item_data['tags'] = [{'name': 'test'}]
        item_data['private'] = True

        view = self.window.active_view()
        text = view.substr(sublime.Region(0, view.size()))
        item_data['body'] = text

        return bytes(json.dumps(item_data), 'UTF-8')


class UpdateItemThread(threading.Thread):

    def __init__(self, window, uuid):
        self.window = window
        self.uuid = uuid
        threading.Thread.__init__(self)

    def run(self):
        data = self.get_item_data()
        url = BASE_URL + '/items/%s?token=%s' % ( self.uuid, qiita_token)

        req = urllib.request.Request(url, data=data, headers=HEADERS, method='PUT')
        res = api_request(req)

        webbrowser.open_new_tab(res.get('url'))

    def get_item_data(self):
        qiita_item = self.window.active_view().settings().get('qiita_item')
        item_data = {}

        item_data['title'] = qiita_item.get('title')
        item_data['tags'] = qiita_item.get('tags')

        view = self.window.active_view()
        item_data['body'] = view.substr(sublime.Region(0, view.size()))

        return bytes(json.dumps(item_data), 'UTF-8')

class GetItemsThread(threading.Thread):

    def __init__(self, window):
        self.window = window
        threading.Thread.__init__(self)

    def run(self):
        url = BASE_URL + '/users/%s/items?token=%s' % (qiita_user, qiita_token)
        self.full_items = api_request(url)

        items = []
        for item in self.full_items:
            title = item.get('title')
            updated_at_in_words = item.get('updated_at_in_words')
            tag_str = ''
            for tag in item.get('tags'):
                if tag_str != '':
                    tag_str += ', '
                tag_str += tag.get('name')

            item_info = [title, "更新：" + updated_at_in_words + " タグ：" + tag_str]
            items.append(item_info)

        self.window.show_quick_panel(items, self.on_done)

    def on_done(self, index):
        if index == -1:
            return

        uuid = self.full_items[index].get('uuid')
        thread = GetItemThread(self.window, uuid)
        thread.start()
        ThreadProgress(thread, 'Geting item from qiita', 'Done.')


class GetItemThread(threading.Thread):

    def __init__(self, window, uuid):
        self.window = window
        self.uuid = uuid
        threading.Thread.__init__(self)

    def run(self):
        url = BASE_URL + '/items/%s?token=%s' % (self.uuid, qiita_token)

        item = api_request(url)

        view = sublime.active_window().new_file()
        self.build_view(view, item)

        # info_view = self.window.create_output_panel('qiita_info')
        # info_view.run_command('append', {'characters': 'タイトル: %s\n' % item.get('title')})
        # info_view.run_command('append', {'characters': '更新時間: %s\n' % item.get('updated_at')})
        # info_view.run_command('append', {'characters': '作成時間: %s\n' % item.get('created_at')})

        # self.window.run_command('show_panel', {'panel': 'output.qiita_info'})
    def build_view(self, view, item):
        view.settings().set('qiita_item', item)

        view.run_command('append', {'characters': item.get('raw_body')})


